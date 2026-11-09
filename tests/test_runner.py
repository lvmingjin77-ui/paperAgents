"""Runner contract and unit-level statistics on a synthetic evaluator (no model or real experiment)."""

import json
import sys

import pytest

from paperagents.runner import compare_results, run_experiment

EVALUATOR = """import argparse, json, pathlib
p = argparse.ArgumentParser()
for name in ('program', 'data', 'seed', 'output'): p.add_argument('--' + name)
a = p.parse_args()
o = pathlib.Path(a.output)
program = json.loads(pathlib.Path(a.program).read_text())
data = json.loads(pathlib.Path(a.data).read_text())
if program.get('crash'): raise SystemExit(3)
values = {'accuracy': data['base'] + program['gain'], 'far': program['far']}
spread = [program['gain'] * (i - 1) * 0.1 for i in range(len(data['units']))]
units = {u: {k: [v + d, 1] for k, v in values.items()} for u, d in zip(data['units'], spread)}
if program.get('inconsistent'): values['far'] += 0.5
(o / 'metrics.json').write_text(json.dumps(values))
(o / 'units.json').write_text(json.dumps(units))
(o / 'correct.json').write_text(json.dumps({'correct': True}))
"""


@pytest.fixture
def setup(tmp_path):
    workspace = tmp_path / "input"
    workspace.mkdir()
    (workspace / "evaluate.py").write_text(EVALUATOR)
    (workspace / "base.json").write_text(json.dumps({"gain": 0.0, "far": 0.1}))
    (workspace / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.05}))
    for split, base in (("screen", 0.5), ("confirm", 0.6), ("test", 0.7)):
        (workspace / f"{split}.json").write_text(json.dumps({"base": base, "units": ["g1", "g2", "g3"]}))
    protocol = {
        "protocol_id": "fixture",
        "evaluator": "evaluate.py",
        "programs": {"baseline": "base.json", "candidate": "candidate.json"},
        "splits": {s: f"{s}.json" for s in ("screen", "confirm", "test")},
        "metrics": {"accuracy": {"direction": "max"}, "far": {"direction": "min"}},
        "assets": [],
    }
    config = {
        "resources": {"python_executable": sys.executable},
        "execution": {"sandbox": "none", "experiment_timeout_seconds": 10},
    }
    return workspace, protocol, config


def run(setup, tmp_path, program, name, seed=1):
    workspace, protocol, config = setup
    return run_experiment(workspace, tmp_path / name, protocol, program, "screen", seed, config)


def test_units_reproduce_metrics_and_paired_bootstrap(setup, tmp_path):
    base = [run(setup, tmp_path, "baseline", f"b{s}", s) for s in (1, 2)]
    cand = [run(setup, tmp_path, "candidate", f"c{s}", s) for s in (1, 2)]
    assert all(r["outcome"] == "completed" for r in base + cand)
    assert not (tmp_path / "c1" / "workspace" / "test.json").exists()  # only the selected split is staged
    assert run(setup, tmp_path, "baseline", "b1") == base[0]  # a receipt is never re-executed
    result = compare_results(base, cand, setup[1]["metrics"])
    assert result["pareto_relation"] == "candidate_dominates"
    accuracy = result["unit_bootstrap"]["accuracy"]
    assert accuracy["improvement"][0] == pytest.approx(0.2) and accuracy["n_units"] == 3
    assert accuracy["baseline"][1] is None  # identical resamples bound nothing


@pytest.mark.parametrize(("flag", "outcome"), [("crash", "impl_failed"), ("inconsistent", "protocol_failed")])
def test_failures_are_recorded_not_scored(setup, tmp_path, flag, outcome):
    (setup[0] / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.05, flag: True}))
    assert run(setup, tmp_path, "candidate", "c")["outcome"] == outcome


def test_unresolved_metric_is_not_domination(setup, tmp_path):
    (setup[0] / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.1}))
    base, cand = run(setup, tmp_path, "baseline", "b"), run(setup, tmp_path, "candidate", "c")
    assert compare_results([base], [cand], setup[1]["metrics"])["pareto_relation"] == "unresolved"


def test_sealed_split_and_inputs_stay_protected(setup, tmp_path):
    workspace, protocol, config = setup
    protocol["assets"] = ["."]  # a shared asset directory that also contains the test split
    (workspace / "candidate.json").write_text(json.dumps({"gain": 0.2, "far": 0.05}))
    result = run_experiment(workspace, tmp_path / "c", protocol, "candidate", "screen", 1, config)
    assert result["outcome"] == "completed"
    assert not (tmp_path / "c" / "workspace" / "test.json").exists()
