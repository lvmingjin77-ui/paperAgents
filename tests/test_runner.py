"""Synthetic local programs only: no research, model calls, downloads or external datasets."""

from pathlib import Path
import json
import platform
import shutil
import sys

import pytest

from paperagents.runner import (
    SandboxUnavailable,
    compare_results,
    run_experiment,
    summarize_runs,
    tree_hash,
)


EVALUATOR = """import argparse, json, os, pathlib
p = argparse.ArgumentParser()
for name in ('program', 'data', 'seed', 'output'): p.add_argument('--' + name)
a = p.parse_args()
o = pathlib.Path(a.output)
program = json.loads(pathlib.Path(a.program).read_text())
data = json.loads(pathlib.Path(a.data).read_text())
if program.get('sleep'):
    import time
    time.sleep(30)
assert not os.environ.get('ZHIPU_API_KEY')
assert not os.environ.get('ANTHROPIC_AUTH_TOKEN')
assert not pathlib.Path('sealed.json').exists() or data.get('test')
values = {'accuracy': data['base'] + program['gain'], 'far': program['far']}
if program.get('missing'): values.pop('far')
if program.get('tamper'): pathlib.Path(a.program).write_text('{}')
(o / 'metrics.json').write_text(json.dumps(values))
(o / 'correct.json').write_text(json.dumps({'correct': not program.get('invalid', False)}))
"""


@pytest.fixture
def setup(tmp_path):
    workspace = tmp_path / "input"
    workspace.mkdir()
    (workspace / "evaluate.py").write_text(EVALUATOR)
    (workspace / "base.json").write_text(json.dumps({"gain": 0.0, "far": 0.1}))
    (workspace / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.05}))
    (workspace / "screen.json").write_text(json.dumps({"base": 0.5}))
    (workspace / "confirm.json").write_text(json.dumps({"base": 0.6}))
    (workspace / "sealed.json").write_text(json.dumps({"base": 0.7, "test": True}))
    protocol = {
        "protocol_id": "fixture-v1",
        "evaluator": "evaluate.py",
        "programs": {"baseline": "base.json", "candidate": "candidate.json"},
        "splits": {"screen": "screen.json", "confirm": "confirm.json", "test": "sealed.json"},
        "metrics": {"accuracy": {"direction": "max"}, "far": {"direction": "min"}},
    }
    config = {
        "resources": {"python_executable": sys.executable},
        "execution": {"sandbox": "none", "experiment_timeout_seconds": 3},
    }
    return workspace, protocol, config


def test_valid_receipts_and_paired_comparison(setup, tmp_path, monkeypatch):
    workspace, protocol, config = setup
    monkeypatch.setenv("ZHIPU_API_KEY", "synthetic-do-not-propagate")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "synthetic-do-not-propagate")
    baselines, candidates = [], []
    for seed in (1, 2, 3):
        baselines.append(
            run_experiment(workspace, tmp_path / f"base{seed}", protocol, "baseline", "screen", seed, config)
        )
        candidates.append(
            run_experiment(
                workspace, tmp_path / f"candidate{seed}", protocol, "candidate", "screen", seed, config
            )
        )
    assert all(r["outcome"] == "completed" for r in baselines + candidates)
    assert (
        run_experiment(workspace, tmp_path / "base1", protocol, "baseline", "screen", 1, config)
        == baselines[0]
    )
    result = compare_results(baselines, candidates, protocol["metrics"])
    assert result["pareto_relation"] == "candidate_dominates_observed_means"
    assert result["paired_seeds"] == [1, 2, 3]
    assert result["paired_improvement"]["accuracy"]["mean"] == pytest.approx(0.2)
    assert result["baseline"]["metrics"]["accuracy"]["ci95"] == [0.5, 0.5]
    stage = tmp_path / "candidate1" / "workspace"
    assert not (stage / "sealed.json").exists()
    assert not (stage / "confirm.json").exists()
    assert Path(candidates[0]["artifact_refs"][0]).is_file()
    with pytest.raises(ValueError, match="different inputs"):
        run_experiment(workspace, tmp_path / "base1", protocol, "baseline", "screen", 9, config)


def test_protocol_and_program_identity_are_independent_of_other_candidates(setup, tmp_path):
    workspace, protocol, config = setup
    baseline_protocol = dict(protocol, programs={"baseline": "base.json"})
    first = run_experiment(workspace, tmp_path / "base1", baseline_protocol, "baseline", "screen", 1, config)
    (workspace / "unrelated-candidate.json").write_text('{"gain": 999}')
    second = run_experiment(workspace, tmp_path / "base2", baseline_protocol, "baseline", "screen", 2, config)
    candidate = run_experiment(workspace, tmp_path / "candidate", protocol, "candidate", "screen", 1, config)
    assert first["protocol_hash"] == second["protocol_hash"] == candidate["protocol_hash"]
    assert first["code_hash"] == second["code_hash"] != candidate["code_hash"]
    assert first["program_hash"] == second["program_hash"] != candidate["program_hash"]
    assert first["workspace_hash"] != second["workspace_hash"]
    assert summarize_runs([first, second], protocol["metrics"])["completed"] == 2
    assert compare_results([first], [candidate], protocol["metrics"])["paired_seeds"] == [1]
    assert (
        run_experiment(workspace, tmp_path / "base1", baseline_protocol, "baseline", "screen", 1, config)
        == first
    )
    stage = tmp_path / "base2" / "workspace"
    assert not (stage / "candidate.json").exists()
    assert not (stage / "unrelated-candidate.json").exists()


def test_declared_dependencies_are_staged_and_invalidate_the_shared_contract(setup, tmp_path):
    workspace, protocol, config = setup
    (workspace / "shared.py").write_text("OFFSET = 0\n")
    (workspace / "evaluate.py").write_text("import shared\n" + EVALUATOR)
    protocol["assets"] = ["shared.py"]
    first = run_experiment(workspace, tmp_path / "base", protocol, "baseline", "screen", 1, config)
    assert first["outcome"] == "completed"
    assert (tmp_path / "base" / "workspace" / "shared.py").is_file()
    (workspace / "shared.py").write_text("OFFSET = 1\n")
    second = run_experiment(workspace, tmp_path / "candidate", protocol, "candidate", "screen", 1, config)
    assert first["protocol_hash"] != second["protocol_hash"]
    with pytest.raises(ValueError, match="share the protocol"):
        compare_results([first], [second], protocol["metrics"])
    with pytest.raises(ValueError, match="different inputs"):
        run_experiment(workspace, tmp_path / "base", protocol, "baseline", "screen", 1, config)


def test_runtime_assets_cannot_smuggle_sealed_data(setup, tmp_path):
    workspace, protocol, config = setup
    protocol["assets"] = ["sealed.json"]
    with pytest.raises(ValueError, match="non-selected data split"):
        run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)


def test_development_and_final_split_cannot_be_same_file(setup, tmp_path):
    workspace, protocol, config = setup
    protocol["splits"]["test"] = protocol["splits"]["screen"]
    with pytest.raises(ValueError, match="must be distinct"):
        run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)


@pytest.mark.parametrize(
    ("setting", "expected"),
    [
        ("invalid", "protocol_failed"),
        ("missing", "protocol_failed"),
        ("tamper", "protocol_failed"),
        ("sleep", "budget_exhausted"),
    ],
)
def test_failed_protocol_and_timeout_keep_evidence(setup, tmp_path, setting, expected):
    workspace, protocol, config = setup
    (workspace / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.05, setting: True}))
    config["execution"]["experiment_timeout_seconds"] = 0.15 if setting == "sleep" else 3
    result = run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)
    assert result["outcome"] == expected
    assert (tmp_path / "run" / "receipt.json").is_file()
    assert result["elapsed_seconds"] < 5


def test_crash_is_implementation_failure(setup, tmp_path):
    workspace, protocol, config = setup
    (workspace / "evaluate.py").write_text('raise RuntimeError("synthetic crash")')
    result = run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)
    assert result["outcome"] == "impl_failed"
    assert "synthetic crash" in (tmp_path / "run" / "driver.log").read_text()


def test_auto_never_silently_disables_sandbox(setup, tmp_path, monkeypatch):
    workspace, protocol, config = setup
    config["execution"]["sandbox"] = "auto"
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(SandboxUnavailable):
        run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)
    assert not (tmp_path / "run" / "driver.log").exists()


def test_input_validation_and_hashes(setup, tmp_path):
    workspace, protocol, config = setup
    before = tree_hash(workspace)
    (workspace / "base.json").write_text("{}")
    assert tree_hash(workspace) != before
    protocol["splits"]["test"] = "../outside.json"
    (tmp_path / "outside.json").write_text("{}")
    with pytest.raises(ValueError, match="inside workspace"):
        run_experiment(workspace, tmp_path / "run", protocol, "candidate", "screen", 1, config)


def test_uncertainty_and_tradeoffs():
    metrics = {"accuracy": {"direction": "max"}, "far": {"direction": "min"}}

    def record(seed, program, accuracy, far):
        return {
            "seed": seed,
            "program": program,
            "protocol_id": "test",
            "split": "screen",
            "code_hash": program,
            "outcome": "completed",
            "metrics": {"accuracy": accuracy, "far": far},
        }

    baseline = [record(1, "base", 0.7, 0.1), record(2, "base", 0.8, 0.1)]
    candidate = [record(1, "candidate", 0.8, 0.2), record(2, "candidate", 0.9, 0.2)]
    assert compare_results(baseline, candidate, metrics)["pareto_relation"] == "tradeoff"
    assert summarize_runs(baseline[:1], metrics)["metrics"]["accuracy"]["ci95"] is None
    with pytest.raises(ValueError, match="Duplicate seed"):
        summarize_runs(baseline + baseline, metrics)
    candidate[0]["split"] = "test"
    with pytest.raises(ValueError):
        compare_results(baseline, candidate, metrics)


@pytest.mark.skipif(
    platform.system() != "Darwin" or not shutil.which("sandbox-exec"), reason="macOS sandbox only"
)
def test_macos_sandbox_executes_valid_program_and_blocks_external_write(setup, tmp_path):
    workspace, protocol, config = setup
    config["execution"]["sandbox"] = "auto"
    result = run_experiment(workspace, tmp_path / "valid", protocol, "candidate", "screen", 1, config)
    assert result["outcome"] == "completed", (tmp_path / "valid" / "driver.log").read_text()
    outside = tmp_path / "must-not-exist"
    (workspace / "evaluate.py").write_text(
        f'from pathlib import Path\nPath({str(outside)!r}).write_text("no")'
    )
    result = run_experiment(workspace, tmp_path / "denied", protocol, "candidate", "screen", 2, config)
    assert result["outcome"] == "impl_failed"
    assert not outside.exists()


@pytest.mark.skipif(
    platform.system() != "Darwin" or not shutil.which("sandbox-exec"), reason="macOS sandbox only"
)
def test_macos_blocks_network_and_original_sealed_data(setup, tmp_path):
    workspace, protocol, config = setup
    config["execution"]["sandbox"] = "auto"
    (workspace / "evaluate.py").write_text('import socket\nsocket.socket().bind(("127.0.0.1", 0))')
    network = run_experiment(workspace, tmp_path / "network", protocol, "candidate", "screen", 1, config)
    assert network["outcome"] == "impl_failed"
    (workspace / "evaluate.py").write_text(
        f"from pathlib import Path\nPath({str(workspace / 'sealed.json')!r}).read_text()"
    )
    sealed = run_experiment(workspace, tmp_path / "sealed", protocol, "candidate", "screen", 1, config)
    assert sealed["outcome"] == "impl_failed"
