from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from paperagents import writing


@pytest.fixture
def state():
    return {
        "claims": {
            "a@1": {"claim_id": "a", "version": 1, "text": "An empirical claim", "verdict": "supported"}
        },
        "protocol": {"protocol_id": "p1"},
        "evidence": {},
        "frozen": {},
        "runs": {
            "r1": {
                "outcome": "completed",
                "claim_ref": "a@1",
                "metrics": {"score": 0.75},
                "split": "screen",
                "seed": 1,
            },
            "broken": {
                "outcome": "impl_failed",
                "claim_ref": "a@1",
                "metrics": {"score": 99},
                "split": "screen",
            },
        },
        "knowledge": {
            "corpus": {
                "papers": [
                    {
                        "paper_id": "p1",
                        "title": "Source paper",
                        "year": 2025,
                        "authors": ["A Author"],
                        "doi": "10.000/test",
                    }
                ]
            }
        },
    }


@pytest.fixture
def content():
    return {
        "title": "Evidence & Methods",
        "sections": [
            {
                "name": "Results",
                "claim_refs": ["a@1"],
                "tex": r"The measured score is \metric{r1}{score}. See \cite{source}.",
            }
        ],
        "references": [{"key": "source", "paper_id": "p1", "title": "Source paper"}],
    }


def test_materialized_values_and_sources_are_bound(tmp_path, state, content):
    result = writing.materialize_draft(tmp_path, state, content, {})
    directory = Path(result["path"])
    assert result["audit"]["passed"]
    assert "0.75" in (directory / "metrics.tex").read_text()
    assert "broken" not in (directory / "metrics.tex").read_text()
    assert "A Author" in (directory / "references.bib").read_text()
    assert "Anonymous Authors" in (directory / "main.tex").read_text()
    assert writing.materialize_draft(tmp_path, state, content, {})["version"] == result["version"]


@pytest.mark.parametrize("change", ["claim", "citation", "metric", "other_version", "file_read"])
def test_writer_cannot_claim_unrecorded_evidence(tmp_path, state, content, change):
    if change == "claim":
        content["sections"][0]["claim_refs"] = ["unknown@9"]
    elif change == "citation":
        content["sections"][0]["tex"] = r"\cite{invented}"
    elif change == "metric":
        content["sections"][0]["tex"] = r"\metric{broken}{score}"
    elif change == "other_version":
        state["claims"]["a@2"] = deepcopy(state["claims"]["a@1"])
        content["sections"][0]["claim_refs"] = ["a@2"]
    else:
        content["sections"][0]["tex"] = r"\input{/etc/passwd}"
    with pytest.raises(ValueError):
        writing.materialize_draft(tmp_path, state, content, {})


def test_reference_metadata_is_taken_from_library(tmp_path, state, content):
    content["references"][0]["title"] = "Invented source"
    with pytest.raises(ValueError, match="disagrees"):
        writing.materialize_draft(tmp_path, state, content, {})


def test_freeze_is_detached_and_excludes_holdout(state):
    state["runs"]["test"] = dict(state["runs"]["r1"], split="test")
    frozen = writing.freeze_snapshot(state, ["a@1"])
    state["claims"]["a@1"]["text"] = "Modified"
    assert frozen["claims"]["a@1"]["text"] == "An empirical claim"
    assert "test" not in frozen["runs"]


def test_mutation_is_detected(tmp_path, state, content):
    directory = Path(writing.materialize_draft(tmp_path, state, content, {})["path"])
    (directory / "metrics.tex").write_text("fabricated")
    assert not writing.audit_draft(directory)["passed"]
    assert writing.compile_draft(directory)["status"] == "invalid_sources"


def test_missing_compiler_is_not_success(tmp_path, state, content, monkeypatch):
    directory = Path(writing.materialize_draft(tmp_path, state, content, {})["path"])
    monkeypatch.setattr(writing.shutil, "which", lambda _: None)
    assert writing.compile_draft(directory)["status"] == "unavailable"


def test_compile_uses_real_exit_and_pdf(tmp_path, state, content, monkeypatch):
    directory = Path(writing.materialize_draft(tmp_path, state, content, {})["path"])
    monkeypatch.setattr(writing.shutil, "which", lambda name: "/tool/latexmk" if name == "latexmk" else None)

    def execute(command, **kwargs):
        assert "-no-shell-escape" in command
        assert "-norc" in command
        assert kwargs["env"]["openin_any"] == "p"
        assert kwargs["env"]["openout_any"] == "p"
        assert "TEST_API_KEY" not in kwargs["env"]
        (directory / "main.pdf").write_bytes(b"%PDF fixture")
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("TEST_API_KEY", "test-only-secret")
    monkeypatch.setattr(writing.subprocess, "run", execute)
    assert writing.compile_draft(directory)["status"] == "compiled"


def test_local_conference_template(tmp_path, state, content):
    template = tmp_path / "format"
    template.mkdir()
    (template / "header.tex").write_text(
        r"\documentclass{article}\title{%%PAPERAGENTS_TITLE%%}\author{%%PAPERAGENTS_AUTHORS%%}\begin{document}\maketitle"
    )
    result = writing.materialize_draft(
        tmp_path / "run", state, content, {"output": {"template": str(template)}}
    )
    assert "Evidence \\& Methods" in Path(result["main"]).read_text()


@pytest.mark.parametrize(
    "command",
    [
        r"\input{/etc/passwd}",
        r"\input /etc/passwd",
        r"\includegraphics{../../private.png}",
        r"\openin1=secret",
        r"\usepackage{/tmp/external}",
    ],
)
def test_template_file_access_is_audited_before_compile(tmp_path, state, content, command, monkeypatch):
    template = tmp_path / "format"
    template.mkdir()
    (template / "header.tex").write_text(r"\documentclass{article}\begin{document}" + command)
    result = writing.materialize_draft(
        tmp_path / "run", state, content, {"output": {"template": str(template)}}
    )
    assert not result["audit"]["passed"]
    monkeypatch.setattr(
        writing.shutil, "which", lambda _: pytest.fail("Invalid sources must not invoke a compiler")
    )
    assert writing.compile_draft(Path(result["path"]))["status"] == "invalid_sources"


def test_outline_tracks_evidence_without_promoting_claims(tmp_path, state):
    state["claims"]["a@1"]["verdict"] = "untested"
    state["evidence"]["e1"] = {"claim_ref": "a@1", "kind": "run", "source": "r1", "hash": "receipt"}
    state["runs"]["holdout"] = dict(state["runs"]["r1"], split="test", metrics={"score": 0.98765})
    result = writing.update_outline(tmp_path, state, {"output": {"venue": "Example"}})
    outline = Path(result["path"]).read_text()
    assert "untested" in outline and "`e1`" in outline and "`a@1`" in outline
    assert "0.75" in outline and "0.98765" not in outline and "99" not in outline
    assert "Source paper" in outline
    assert writing.update_outline(tmp_path, state, {})["hash"] != result["hash"]
    state["claims"]["a@1"]["verdict"] = "refuted"
    updated = writing.update_outline(tmp_path, state, {"output": {"venue": "Example"}})
    assert updated["hash"] != result["hash"]
    assert "refuted" in Path(updated["path"]).read_text()


@pytest.fixture
def figure_state(state):
    state["runs"]["r1"].update(
        protocol_id="p1", protocol_hash="protocol-v1", code_hash="code-v1", program="candidate"
    )
    state["runs"]["r2"] = dict(state["runs"]["r1"], code_hash="code-v2", metrics={"score": 0.9})
    state["runs"]["baseline"] = dict(
        state["runs"]["r1"], claim_ref=None, program="baseline", metrics={"score": 0.5}
    )
    state["runs"]["other_protocol"] = dict(
        state["runs"]["r1"], protocol_hash="protocol-v2", metrics={"score": 42}
    )
    state["evidence"]["measured"] = {"kind": "run", "claim_ref": "a@1", "content": {"run_id": "r1"}}
    return state


def test_figures_preserve_protocol_and_implementation_provenance(tmp_path, figure_state):
    figures = writing.generate_figures(tmp_path, figure_state)
    assert len(figures) == 1  # The other protocol has no baseline for comparison.
    figure = figures[0]
    assert set(figure["run_ids"]) == {"baseline", "r1", "r2"}
    assert figure["sources"]["r1"]["code_hash"] != figure["sources"]["r2"]["code_hash"]
    assert figure["claim_refs"] == ["a@1"] and figure["evidence_ids"] == ["measured"]
    assert Path(figure["path"]).read_bytes().startswith(b"%PDF")
    assert Path(figure["preview_path"]).read_bytes().startswith(b"\x89PNG")
    assert writing.generate_figures(tmp_path / "empty", {"runs": {}}) == []


def test_generated_figure_is_embedded_and_audited(tmp_path, figure_state, content):
    figure = writing.generate_figures(tmp_path, figure_state)[0]
    content["figures"] = [figure]
    result = writing.materialize_draft(tmp_path, figure_state, content, {})
    draft = Path(result["path"])
    assert result["audit"]["passed"]
    assert (draft / figure["asset_path"]).read_bytes() == Path(figure["path"]).read_bytes()
    assert figure["asset_path"] in (draft / "sections/00.tex").read_text()
    Path(figure["path"]).write_bytes(b"changed")
    assert not writing.audit_draft(draft)["passed"]


def test_unregistered_or_stale_figure_is_rejected(tmp_path, figure_state, content):
    content["figures"] = [{"path": str(tmp_path / "outside.pdf"), "claim_refs": ["a@1"], "run_ids": ["r1"]}]
    with pytest.raises(ValueError, match="catalog"):
        writing.materialize_draft(tmp_path, figure_state, content, {})
    figure = writing.generate_figures(tmp_path, figure_state)[0]
    content["figures"] = [figure]
    figure_state["runs"]["r1"]["metrics"]["score"] = 99
    with pytest.raises(ValueError, match="changed"):
        writing.materialize_draft(tmp_path, figure_state, content, {})
