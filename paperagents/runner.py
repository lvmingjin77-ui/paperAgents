"""Local experiment execution and unit-level statistics, independent of any agent framework.

The evaluator is called as ``--program PATH --data PATH --seed INT --output PATH`` and writes
``metrics.json``, ``correct.json`` ({"correct": bool}) and ``units.json``
({unit: {metric: [numerator, denominator]}}). A unit is the protocol's independent statistical
unit, and every metric equals the sum of its numerators over the sum of its denominators.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import signal
import statistics
import subprocess
import sys
import time

from .storage import digest, read_json, write_json


def tree_hash(path: Path) -> str:
    """Hash relative names and contents of a file or directory, ignoring Python caches."""
    path = Path(path)
    hasher = hashlib.sha256()
    for item in [path] if path.is_file() else sorted(path.rglob("*")):
        if item.is_file() and "__pycache__" not in item.parts:
            hasher.update((item.name if path.is_file() else item.relative_to(path).as_posix()).encode() + b"\0")
            hasher.update(item.read_bytes())
    return hasher.hexdigest()


def _stage(workspace: Path, destination: Path, protocol: dict, program: str, split: str) -> None:
    """Copy only the evaluator, baseline, this program, this split and declared assets.

    Other splits are never copied, even when they sit inside a declared asset directory.
    """
    hidden = {(workspace / path).resolve() for name, path in protocol["splits"].items() if name != split}
    names = [protocol["evaluator"], protocol["programs"]["baseline"], protocol["programs"][program],
             protocol["splits"][split], *protocol["assets"]]
    for name in dict.fromkeys(names):
        source, target = workspace / name, destination / name
        if source.resolve() in hidden:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True,
                            ignore=lambda d, items: [i for i in items if (Path(d) / i).resolve() in hidden])
        else:
            shutil.copy2(source, target)


def _sandbox(argv: list[str], stage: Path, output: Path, python: Path, mode: str) -> list[str]:
    """No network, read the staged inputs and runtime, write only the output directory."""
    if mode == "none":
        return argv
    runtime = [stage, output, python.resolve().parent.parent, Path(sys.prefix)]
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        reads = " ".join(f"(subpath {json.dumps(str(p))})" for p in runtime + [Path(p) for p in
                         ("/System", "/usr", "/bin", "/sbin", "/Library", "/private/var/db", "/dev")])
        profile = output / "sandbox.sb"
        profile.write_text("\n".join([
            "(version 1)", "(deny default)", "(allow process*)", "(allow sysctl-read)", "(allow mach-lookup)",
            "(allow ipc-posix*)", "(allow iokit-open)", "(allow file-read-metadata)", "(allow file-map-executable)",
            '(allow file-read-data (literal "/"))', f"(allow file-read* {reads})",
            f'(allow file-write* (subpath {json.dumps(str(output))}) (literal "/dev/null"))',
            f"(deny file-write* (subpath {json.dumps(str(stage))}))", "(deny network*)",
        ]))
        return [shutil.which("sandbox-exec"), "-f", str(profile), *argv]
    if platform.system() == "Linux" and shutil.which("bwrap"):
        command = [shutil.which("bwrap"), "--unshare-all", "--die-with-parent", "--proc", "/proc", "--dev", "/dev",
                   "--tmpfs", "/tmp"]
        for path in [Path(p) for p in ("/usr", "/bin", "/lib", "/lib64")] + runtime[2:]:
            if path.exists():
                command += ["--ro-bind", str(path), str(path)]
        # The output bind comes first so the staged inputs inside it stay read-only.
        return command + ["--bind", str(output), str(output), "--ro-bind", str(stage), str(stage), *argv]
    raise ValueError('No experiment sandbox (sandbox-exec or bwrap); set execution.sandbox = "none" explicitly')


def run_experiment(workspace: Path, output_dir: Path, protocol: dict, program: str, split: str, seed: int,
                   config: dict) -> dict:
    """Execute one program/split/seed once and keep its receipt; an existing receipt is returned."""
    workspace, output_dir = Path(workspace).resolve(), Path(output_dir).resolve()
    receipt_path = output_dir / "receipt.json"
    if receipt_path.exists():
        return read_json(receipt_path)
    execution = config["execution"]
    python = Path(config["resources"]["python_executable"] or sys.executable).absolute()
    stage, results = output_dir / "workspace", output_dir / "results"
    for directory in (results, output_dir / "tmp", output_dir / "home"):
        directory.mkdir(parents=True, exist_ok=True)
    _stage(workspace, stage, protocol, program, split)
    common = [protocol["evaluator"], protocol["programs"]["baseline"], *protocol["splits"].values(), *protocol["assets"]]
    receipt = dict(
        protocol_id=protocol["protocol_id"],
        protocol_hash=digest({name: tree_hash(workspace / name) for name in common}),
        program=program,
        code_hash=tree_hash(workspace / protocol["programs"][program]),
        split=split,
        seed=seed,
        outcome="impl_failed",
        metrics={},
    )
    argv = [str(python), "-B", str(stage / protocol["evaluator"]), "--program", str(stage / protocol["programs"][program]),
            "--data", str(stage / protocol["splits"][split]), "--seed", str(seed), "--output", str(results)]
    # An allowlisted environment: model API tokens and shell configuration never reach the experiment.
    env = {"PATH": f"{python.parent}{os.pathsep}/usr/bin:/bin", "LANG": "en_US.UTF-8", "HOME": str(output_dir / "home"),
           "TMPDIR": str(output_dir / "tmp"), "PYTHONNOUSERSITE": "1", "HF_HUB_OFFLINE": "1",
           "TRANSFORMERS_OFFLINE": "1", "TZ": "UTC"}
    started, inputs = time.monotonic(), tree_hash(stage)
    try:
        command = _sandbox(argv, stage, output_dir, python, execution["sandbox"])
        with (output_dir / "driver.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=stage, env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                receipt["returncode"] = process.wait(timeout=execution["experiment_timeout_seconds"])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                receipt.update(outcome="budget_exhausted", reason="Experiment time budget exhausted")
            except KeyboardInterrupt:
                # No receipt: a development run is repeated on resume; an opened holdout is not.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        if receipt.get("returncode") == 0:
            metrics, units = read_json(results / "metrics.json"), read_json(results / "units.json")
            for name in protocol["metrics"]:
                total = [sum(units[u][name][i] for u in units) for i in (0, 1)]
                if not total[1] or not math.isclose(total[0] / total[1], metrics[name], rel_tol=1e-9, abs_tol=1e-12):
                    raise ValueError(f"{name}: metrics.json is not reproduced by the unit sums in units.json")
            correct = read_json(results / "correct.json")["correct"] is True
            receipt.update(outcome="completed" if correct else "protocol_failed",
                           metrics={n: metrics[n] for n in protocol["metrics"]}, units_path=str(results / "units.json"))
        elif "returncode" in receipt:
            receipt["reason"] = "Evaluator failed; see driver.log"
        if tree_hash(stage) != inputs:
            receipt.update(outcome="protocol_failed", reason="The experiment modified its own inputs")
    except (OSError, ValueError, KeyError, TypeError) as error:
        receipt.update(outcome="protocol_failed", reason=str(error))
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json(receipt_path, receipt)
    return receipt


def summarize_runs(runs: list[dict], metrics: dict) -> dict:
    """Seed spread of completed runs (algorithmic randomness only)."""
    good = [r for r in runs if r["outcome"] == "completed"]
    return {
        "metrics": {
            name: {"n": len(good), "mean": statistics.mean(r["metrics"][name] for r in good) if good else None,
                   "seed_sd": statistics.stdev(r["metrics"][name] for r in good) if len(good) > 1 else None}
            for name in metrics
        },
        "outcomes": {k: sum(r["outcome"] == k for r in runs)
                     for k in ("completed", "impl_failed", "protocol_failed", "budget_exhausted")},
    }


def _unit_table(runs: list[dict], metrics: dict) -> dict:
    """Average each unit's numerator and denominator over completed seeds."""
    tables = [read_json(Path(r["units_path"])) for r in runs if r["outcome"] == "completed"]
    if not tables:
        return {}
    return {u: {m: [sum(t[u][m][i] for t in tables) / len(tables) for i in (0, 1)] for m in metrics} for u in tables[0]}


def _ratio(table: dict, units: list, metric: str) -> float | None:
    den = sum(table[u][metric][1] for u in units)
    return sum(table[u][metric][0] for u in units) / den if den else None


def compare_results(baseline_runs: list[dict], candidate_runs: list[dict], metrics: dict, draws: int = 2000) -> dict:
    """Paired bootstrap over independent statistical units; no claim is accepted automatically."""
    hashes = {r["protocol_hash"] for r in baseline_runs + candidate_runs if r["outcome"] == "completed"}
    if len(hashes) > 1:
        raise ValueError("Baseline and candidate runs used different evaluation contracts")
    base, cand = _unit_table(baseline_runs, metrics), _unit_table(candidate_runs, metrics)
    units = sorted(base) if base and cand and set(base) == set(cand) else []
    rng = random.Random(0)
    samples = [[rng.choice(units) for _ in units] for _ in range(draws)] if units else []

    def interval(fn):
        # Identical resamples (e.g. zero events in every unit) bound nothing; never report [x, x].
        values = sorted(v for v in map(fn, samples) if v is not None)
        if not values or values[0] == values[-1]:
            return None
        return [values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]]

    bootstrap, signs = {}, []
    for name, spec in metrics.items() if units else ():
        sign = 1 if spec["direction"] == "max" else -1

        def gain(sample, name=name, sign=sign):
            b, c = _ratio(base, sample, name), _ratio(cand, sample, name)
            return None if b is None or c is None else sign * (c - b)

        ci = interval(gain)
        bootstrap[name] = {
            "baseline": [_ratio(base, units, name), interval(lambda u, n=name: _ratio(base, u, n))],
            "candidate": [_ratio(cand, units, name), interval(lambda u, n=name: _ratio(cand, u, n))],
            "improvement": [gain(units), ci],
            "n_units": len(units),
        }
        signs.append(0 if ci is None else (1 if ci[0] > 0 else -1 if ci[1] < 0 else 0))
    # An unresolved metric is not evidence of non-inferiority, so domination needs every metric resolved.
    relation = "insufficient_paired_evidence"
    if signs:
        relation = ("tradeoff" if 1 in signs and -1 in signs else "unresolved" if 0 in signs
                    else "candidate_dominates" if signs[0] > 0 else "baseline_dominates")
    return {
        "baseline": summarize_runs(baseline_runs, metrics),
        "candidate": summarize_runs(candidate_runs, metrics),
        "unit_bootstrap": bootstrap,
        "pareto_relation": relation,
        "uncertainty": "95% percentile intervals from paired resampling of independent units; null when every "
        "resample is identical (e.g. zero events). Seed spread is reported separately.",
    }
