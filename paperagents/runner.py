"""Local experiment execution and descriptive statistics, independent of any agent framework.

The evaluator interface is ``--program PATH --data PATH --seed INT --output PATH``.
Only the selected split is staged. Outputs are immutable per invocation and never treated
as scientific conclusions merely because the process exited successfully.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import time

from .storage import read_json, write_json


class SandboxUnavailable(ValueError):
    """No supported OS sandbox is installed; execution was not attempted."""


def tree_hash(path: Path) -> str:
    """Hash relative names and file contents, excluding transient Python caches."""
    path = Path(path).resolve()
    hasher = hashlib.sha256()
    files = [path] if path.is_file() else sorted(path.rglob("*"))
    for item in files:
        if item.is_symlink():
            raise ValueError(f"Symlinks are not experiment inputs: {item}")
        if not item.is_file() or "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        hasher.update((item.name if path.is_file() else item.relative_to(path).as_posix()).encode())
        hasher.update(b"\0")
        with item.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
    return hasher.hexdigest()


def _inside(root: Path, name: str) -> Path:
    path = root / name
    if Path(name).is_absolute() or not path.resolve().is_relative_to(root) or not path.exists():
        raise ValueError(f"Experiment input must exist inside workspace: {name}")
    if path.is_symlink():
        raise ValueError(f"Experiment input cannot be a symlink: {name}")
    return path


def _stage(workspace: Path, destination: Path, protocol: dict, program: str, split: str) -> None:
    splits = {key: _inside(workspace, value) for key, value in protocol["splits"].items()}
    if len(set(splits.values())) != len(splits):
        raise ValueError("Data split paths must be distinct")
    selected = splits[split]
    hidden = [path for key, path in splits.items() if key != split and path != selected]
    for other in hidden:
        if selected.is_relative_to(other) or other.is_relative_to(selected):
            raise ValueError("Split paths must be separate files or non-overlapping directories")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            path = Path(directory) / name
            if name in {".git", ".venv", "__pycache__"} or name.startswith(".env") or path in hidden:
                ignored.add(name)
        return ignored

    # Undeclared helper code is not executable input. This keeps a program's identity
    # stable when another candidate is added, without overlooking shared dependencies.
    names = [
        protocol["evaluator"],
        protocol["programs"]["baseline"],
        protocol["programs"][program],
        protocol["splits"][split],
        *protocol.get("assets", []),
    ]
    paths = sorted({_inside(workspace, name) for name in names}, key=lambda path: len(path.parts))
    copied = []
    destination.mkdir()
    for path in paths:
        if any(path.is_relative_to(other) for other in hidden):
            raise ValueError("Runtime assets cannot include a non-selected data split")
        if any(path.is_relative_to(parent) for parent in copied):
            continue
        target = destination / path.relative_to(workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, target, ignore=ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target)
        copied.append(path)


def _input_identity(workspace: Path, protocol: dict, program: str, split: str) -> dict:
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    # The baseline, evaluator, declared dependencies and split definitions are the
    # common comparison contract. Candidate implementations are identified separately.
    common = dict(protocol, programs={"baseline": protocol["programs"]["baseline"]})
    common_names = [
        protocol["evaluator"],
        protocol["programs"]["baseline"],
        *protocol["splits"].values(),
        *protocol.get("assets", []),
    ]
    common_hashes = {name: tree_hash(_inside(workspace, name)) for name in common_names}
    names = [
        protocol["evaluator"],
        protocol["programs"]["baseline"],
        protocol["programs"][program],
        protocol["splits"][split],
        *protocol.get("assets", []),
    ]
    inputs = {name: tree_hash(_inside(workspace, name)) for name in names}
    return {
        "protocol_hash": digest({"contract": common, "inputs": common_hashes}),
        "program_hash": inputs[protocol["programs"][program]],
        "code_hash": digest(inputs),
        "input_hashes": inputs,
    }


def _sandbox(argv: list[str], stage: Path, output: Path, python: Path, mode: str) -> tuple[list[str], str]:
    if mode == "none":
        return argv, "none (explicitly unconfined)"
    if mode != "auto":
        raise ValueError("execution.sandbox must be auto or none")
    runtime = python.parent.parent
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        read_roots = [
            stage,
            output,
            runtime,
            python.resolve().parent.parent,
            Path(sys.prefix),
            Path("/System"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/Library"),
            Path("/private/var/db"),
        ]
        read_rules = " ".join("(subpath " + json.dumps(str(p)) + ")" for p in read_roots)
        profile = "\n".join(
            [
                "(version 1)",
                "(deny default)",
                "(allow process*)",
                "(allow sysctl-read)",
                "(allow mach-lookup)",
                "(allow ipc-posix*)",
                "(allow iokit-open)",
                "(allow file-read-metadata)",
                '(allow file-read-data (literal "/"))',
                "(allow file-map-executable)",
                f"(allow file-read* {read_rules})",
                '(allow file-read* (subpath "/dev"))',
                f'(allow file-write* (subpath {json.dumps(str(output))}) (literal "/dev/null"))',
                f"(deny file-write* (subpath {json.dumps(str(stage))}))",
                "(deny network*)",
            ]
        )
        path = output / "sandbox.sb"
        path.write_text(profile)
        return [shutil.which("sandbox-exec"), "-f", str(path), *argv], "macos-seatbelt"
    if platform.system() == "Linux" and shutil.which("bwrap"):
        command = [shutil.which("bwrap"), "--unshare-all", "--die-with-parent", "--new-session"]
        for path in [
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/lib"),
            Path("/lib64"),
            runtime,
            python.resolve().parent.parent,
            Path(sys.prefix),
        ]:
            if path.exists():
                command += ["--ro-bind", str(path), str(path)]
        command += [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(output),
            str(output),
            "--ro-bind",
            str(stage),
            str(stage),
            "--chdir",
            str(stage),
            *argv,
        ]
        return command, "linux-bubblewrap"
    raise SandboxUnavailable(
        "No OS sandbox available. Install bubblewrap on Linux or use macOS "
        'sandbox-exec; execution.sandbox="none" requires an explicit choice.'
    )


def _stop(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    # Children may remain after the group leader exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_experiment(
    workspace: Path, output_dir: Path, protocol: dict, program: str, split: str, seed: int, config: dict
) -> dict:
    """Execute one frozen program/split/seed and preserve its receipt and raw outputs.

    Caller owns scientific approval and final-test authorization. Reusing a receipt returns
    it only for identical inputs. An interrupted invocation has a receipt marked interrupted;
    a new output directory is needed to retry it. No model calls occur here.
    """
    workspace, output_dir = Path(workspace).resolve(), Path(output_dir).resolve()
    if output_dir.is_relative_to(workspace) or workspace.is_relative_to(output_dir):
        raise ValueError("Experiment output and workspace must be separate directory trees")
    evaluator = _inside(workspace, protocol.get("evaluator", "evaluate.py"))
    candidate = _inside(workspace, protocol["programs"][program])
    data = _inside(workspace, protocol["splits"][split])
    metrics = protocol["metrics"]
    if not metrics or any(m.get("direction") not in {"min", "max"} for m in metrics.values()):
        raise ValueError("Protocol metrics require min/max directions")
    if type(seed) is not int:
        raise ValueError("Seed must be an integer")
    execution = config.get("execution", {})
    python = Path(config.get("resources", {}).get("python_executable") or sys.executable).absolute()
    if not python.is_file():
        raise ValueError(f"Python executable not found: {python}")
    mode = execution.get("sandbox", "auto")
    if mode == "auto" and not (
        (platform.system() == "Darwin" and shutil.which("sandbox-exec"))
        or (platform.system() == "Linux" and shutil.which("bwrap"))
    ):
        raise SandboxUnavailable(
            "No supported OS sandbox is available; install bubblewrap on Linux "
            'or explicitly choose execution.sandbox="none".'
        )
    identity = dict(
        _input_identity(workspace, protocol, program, split),
        protocol_id=protocol["protocol_id"],
        program=program,
        split=split,
        seed=seed,
        python=str(python),
        sandbox_mode=execution.get("sandbox", "auto"),
    )
    receipt_path = output_dir / "receipt.json"
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if any(receipt.get(key) != value for key, value in identity.items()):
            raise ValueError("Existing execution receipt belongs to different inputs")
        for name, expected in receipt.get("artifact_hashes", {}).items():
            if not Path(name).is_file() or tree_hash(Path(name)) != expected:
                raise ValueError("Stored experiment outputs changed after execution")
        return receipt
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Unfinished execution directory: preserve it and retry in a new directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    stage, results = output_dir / "workspace", output_dir / "results"
    results.mkdir()
    (output_dir / "tmp").mkdir()
    (output_dir / "home").mkdir()
    workspace_hash = tree_hash(workspace)
    _stage(workspace, stage, protocol, program, split)
    argv = [
        str(python),
        "-B",
        str(stage / evaluator.relative_to(workspace)),
        "--program",
        str(stage / candidate.relative_to(workspace)),
        "--data",
        str(stage / data.relative_to(workspace)),
        "--seed",
        str(seed),
        "--output",
        str(results),
    ]
    command, sandbox = _sandbox(argv, stage, output_dir, python, identity["sandbox_mode"])
    # Build from an allowlist: model API tokens and shell startup configuration never enter.
    env = {
        "PATH": str(python.parent) + os.pathsep + "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
        "HOME": str(output_dir / "home"),
        "TMPDIR": str(output_dir / "tmp"),
        "XDG_CACHE_HOME": str(output_dir / "home" / ".cache"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TZ": "UTC",
    }
    before = tree_hash(stage)
    receipt = dict(
        identity,
        workspace_hash=workspace_hash,
        outcome="impl_failed",
        metrics={},
        command=command,
        sandbox=sandbox,
        artifact_refs=[str(receipt_path), str(output_dir / "driver.log")],
    )
    started = time.monotonic()
    interrupted = False
    try:
        with (output_dir / "driver.log").open("wb") as log:
            process = subprocess.Popen(
                command, cwd=stage, env=env, stdout=log, stderr=log, start_new_session=True
            )
            try:
                receipt["returncode"] = process.wait(
                    timeout=execution.get("experiment_timeout_seconds", 3600)
                )
            except subprocess.TimeoutExpired:
                _stop(process)
                receipt.update(outcome="budget_exhausted", reason="Experiment wall-clock budget exhausted")
            except KeyboardInterrupt:
                _stop(process)
                interrupted = True
                receipt.update(outcome="budget_exhausted", reason="Interrupted by user", interrupted=True)
        if receipt.get("returncode") == 0:
            values = read_json(results / "metrics.json")
            validity = read_json(results / "correct.json")
            receipt["validity"] = validity
            if type(validity.get("correct")) is not bool:
                raise ValueError("correct.json must contain boolean correct")
            if any(
                type(values.get(name)) not in {int, float} or not math.isfinite(values[name])
                for name in metrics
            ):
                raise ValueError("metrics.json lacks a finite numeric value for each protocol metric")
            receipt.update(
                outcome="completed" if validity["correct"] else "protocol_failed",
                metrics={name: values[name] for name in metrics},
                reason=validity.get("reason", ""),
            )
            receipt["artifact_refs"] += [str(results / "metrics.json"), str(results / "correct.json")]
        elif receipt.get("returncode") is not None:
            receipt["reason"] = "Evaluator process failed; inspect driver.log"
        if tree_hash(stage) != before or tree_hash(workspace) != workspace_hash:
            receipt.update(
                outcome="protocol_failed", reason="Reviewed experiment inputs changed during execution"
            )
    except (OSError, ValueError, TypeError) as error:
        receipt.update(outcome="protocol_failed", reason=str(error))
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    receipt["artifact_hashes"] = {
        str(path): tree_hash(path)
        for path in [output_dir / "driver.log", results / "metrics.json", results / "correct.json"]
        if path.is_file()
    }
    write_json(receipt_path, receipt)
    if interrupted:
        raise KeyboardInterrupt
    return receipt


# Two-sided 95% Student t critical values. Each observation is an independent seed,
# never an individual query. A single seed has no estimated confidence interval.
_T95 = (
    0,
    12.706,
    4.303,
    3.182,
    2.776,
    2.571,
    2.447,
    2.365,
    2.306,
    2.262,
    2.228,
    2.201,
    2.179,
    2.160,
    2.145,
    2.131,
    2.120,
    2.110,
    2.101,
    2.093,
    2.086,
    2.080,
    2.074,
    2.069,
    2.064,
    2.060,
    2.056,
    2.052,
    2.048,
    2.045,
    2.042,
)


def _summary(values: list[float]) -> dict:
    count = len(values)
    if not count:
        return {"n": 0, "mean": None, "ci95": None}
    mean = statistics.mean(values)
    ci = None
    if count > 1:
        df = count - 1
        critical = _T95[df] if df <= 30 else (2.042 if df < 60 else (2.000 if df < 120 else 1.980))
        half = critical * statistics.stdev(values) / math.sqrt(count)
        ci = [mean - half, mean + half]
    return {"n": count, "mean": mean, "ci95": ci}


def summarize_runs(runs: list[dict], metrics: dict) -> dict:
    """Summarize valid executions; keep failure counts and unique seed sample size visible."""
    good = [run for run in runs if run["outcome"] == "completed"]
    identities = {
        (r.get("protocol_id"), r.get("protocol_hash"), r.get("split"), r.get("program"), r.get("code_hash"))
        for r in good
    }
    if len(identities) > 1:
        raise ValueError("Cannot pool different programs, protocols, splits or code versions")
    if len({r["seed"] for r in good}) != len(good):
        raise ValueError("Duplicate seed execution is not independent evidence")
    return {
        "metrics": {name: _summary([r["metrics"][name] for r in good]) for name in metrics},
        "completed": len(good),
        "attempted": len(runs),
        "outcomes": {
            kind: sum(r["outcome"] == kind for r in runs)
            for kind in ("completed", "impl_failed", "protocol_failed", "budget_exhausted")
        },
        "uncertainty": "95% Student t intervals across independent seeds; not query-level guarantees.",
    }


def compare_results(baseline_runs: list[dict], candidate_runs: list[dict], metrics: dict) -> dict:
    """Report metric tradeoffs and paired seed deltas; no claim is automatically accepted."""
    baseline, candidate = summarize_runs(baseline_runs, metrics), summarize_runs(candidate_runs, metrics)
    left = {r["seed"]: r for r in baseline_runs if r["outcome"] == "completed"}
    right = {r["seed"]: r for r in candidate_runs if r["outcome"] == "completed"}
    pairs = sorted(left.keys() & right.keys())
    for seed in pairs:
        if any(
            left[seed].get(key) != right[seed].get(key) for key in ("protocol_id", "protocol_hash", "split")
        ):
            raise ValueError("Baseline and candidate must share the protocol and split")
    deltas = {}
    signs = []
    for name, spec in metrics.items():
        sign = 1 if spec["direction"] == "max" else -1
        values = [sign * (right[seed]["metrics"][name] - left[seed]["metrics"][name]) for seed in pairs]
        deltas[name] = dict(_summary(values), positive_means="candidate improves")
        if values:
            tolerance = spec.get("tolerance", 0)
            mean = statistics.mean(values)
            signs.append(1 if mean > tolerance else (-1 if mean < -tolerance else 0))
    relation = "insufficient_paired_evidence"
    if len(signs) == len(metrics):
        if all(s >= 0 for s in signs) and any(s > 0 for s in signs):
            relation = "candidate_dominates_observed_means"
        elif all(s <= 0 for s in signs) and any(s < 0 for s in signs):
            relation = "baseline_dominates_observed_means"
        elif all(s == 0 for s in signs):
            relation = "within_declared_tolerance"
        else:
            relation = "tradeoff"
    return {
        "baseline": baseline,
        "candidate": candidate,
        "paired_seeds": pairs,
        "paired_improvement": deltas,
        "pareto_relation": relation,
        "decision": "Requires independent critic using protocol thresholds, uncertainty and claim scope.",
    }
