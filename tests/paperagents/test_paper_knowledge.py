"""Synthetic v2 fixtures and checks; passing them never establishes paper understanding."""

from copy import deepcopy
import json
import unittest

from paperagents.contracts import artifact_schema, validate_artifact


def paper_v2(paper_id: str = "paper-a", full_text_path: str = "sources/paper-a.md",
             sha256: str = "a" * 64) -> dict:
    """Build a structural fixture. Callers testing files must supply a real path/hash."""
    ref = {"source_id": "main", "anchor_id": "method"}
    pattern = {
        "pattern_id": "matched-control", "name": "Separate mechanism from budget",
        "problem_type": "Confounded improvement", "reasoning_move": "Hold budget fixed while changing mechanism",
        "preconditions": ["Budget can be matched"], "failure_modes": ["Unmeasured confounding"],
        "source_refs": [deepcopy(ref)], "trace_refs": [{"paper_id": paper_id, "trace_id": "design"}],
        "evidence_status": "source_inferred", "transfer_status": "unvalidated",
        "test_plan": "Compare matched-budget conditions in the target task",
    }
    analysis = {name: {"status": "analyzed", "summary": "SYNTHETIC fixture analysis: " + name,
                       "source_refs": [deepcopy(ref)]}
                for name in ("problem", "method", "formalism", "figures_tables", "evidence", "assumptions", "limitations")}
    analysis["formalism"] = {"status": "not_applicable", "summary": "No formal derivation in this fixture",
                             "source_refs": [], "reason": "Synthetic qualitative study"}
    return {
        "expert_id": "paper:" + paper_id, "paper_id": paper_id,
        "knowledge": {
            "paper_understanding": {
                "paper_type": "SYNTHETIC qualitative fixture",
                "sources": [{"source_id": "main", "kind": "full_text", "version": "synthetic-v1",
                             "status": "read", "required": True, "path": full_text_path, "sha256": sha256}],
                "coverage": {"status": "complete", "read_anchor_ids": ["method"], "unread_anchor_ids": []},
                "navigation": [{"anchor_id": "method", "source_id": "main", "kind": "section",
                                "locator": "SYNTHETIC section 1", "summary": "Fixture methods"}],
                "analysis": analysis, "limitations": ["Synthetic fixture, not scientific evidence"],
            },
            "reasoning_patterns": [pattern],
        },
        "idea_trace": [{
            "trace_id": "design", "step": "design", "statement": "A matched control isolates budget",
            "basis": "reconstructed", "source_refs": [deepcopy(ref)], "depends_on": [],
            "reasoning_operation": "Separate competing explanations", "assumptions": ["Comparable budgets"],
            "alternatives": ["Compute alone explains improvement"],
            "testable_implication": "A budget-only explanation predicts no matched-budget improvement",
        }],
        "code_tools": [], "limitations": ["No executable method in this synthetic fixture"],
    }


def domain_v2(source_paper_ids: list[str] | None = None) -> dict:
    """Domain strategies can precede fine-grained paper-expert traces."""
    ids = list(source_paper_ids) if source_paper_ids is not None else ["paper-a"]
    pattern = paper_v2(ids[0])["knowledge"]["reasoning_patterns"][0]
    pattern["source_refs"] = [{"paper_id": ids[0], "locator": "SYNTHETIC section 1"}]
    pattern["trace_refs"] = []
    pattern["trace_link_limitations"] = "Corpus fixture has no stable trace IDs; source locator retained"
    landscape = {"questions": [{"question": "Fixture question", "paper_ids": ids, "known": "SYNTHETIC_TEST_FIXTURE",
                                "unknowns": [], "observations": [], "corpus_gaps": []}],
                 "set_aside": [], "evolution_chains": [], "contested": [], "protocols": [],
                 "gaps": [{"gap_id": "g1", "problem": "Fixture problem", "condition": "fixture", "status": "untested",
                           "evidence_paper_ids": [], "note": "SYNTHETIC_TEST_FIXTURE"}]}
    if len(ids) > 1:
        landscape["evolution_chains"] = [{"chain_id": "c1", "paper_ids": ids[:2], "steps": ["Fixture step"]}]
    return {"expert_id": "domain", "source_paper_ids": ids,
            "knowledge": {"reasoning_patterns": [pattern], "landscape": landscape}, "limitations": []}


class PaperKnowledgeTests(unittest.TestCase):
    def validate(self, data: dict, stage: str = "paper") -> None:
        validate_artifact(stage, data)

    def invalid(self, data: dict, message: str, stage: str = "paper") -> None:
        with self.assertRaisesRegex(ValueError, message):
            self.validate(data, stage)

    def test_valid_paper_and_domain_strategies_need_no_claimed_target_experiment(self):
        self.validate(paper_v2())
        self.validate(domain_v2(), "domain")
        data = paper_v2()
        data["knowledge"]["reasoning_patterns"][0]["evidence_status"] = "source_supported"
        self.validate(data)

    def test_schema_copy_is_independent(self):
        for stage in ("paper", "domain"):
            schema = artifact_schema(stage)
            self.assertEqual(json.loads(json.dumps(schema)), schema)
            schema["properties"].clear()
            self.assertTrue(artifact_schema(stage)["properties"])

    def test_every_analysis_axis_has_content_and_honest_applicability(self):
        for field in paper_v2()["knowledge"]["paper_understanding"]["analysis"]:
            data = paper_v2()
            del data["knowledge"]["paper_understanding"]["analysis"][field]
            self.invalid(data, field)
        data = paper_v2()
        del data["knowledge"]["paper_understanding"]["analysis"]["formalism"]["reason"]
        self.invalid(data, "reason")
        data = paper_v2()
        data["knowledge"]["paper_understanding"]["analysis"]["method"]["source_refs"] = []
        self.invalid(data, "source_refs")

    def test_source_file_verification_is_not_faked_by_the_structural_validator(self):
        data = paper_v2(full_text_path="/nonexistent/synthetic-source")
        self.validate(data)  # The workflow, not this contract, must reject a nonexistent file.
        data["knowledge"]["paper_understanding"]["sources"][0]["sha256"] = "not-a-hash"
        self.invalid(data, "sha256")

    def test_complete_requires_full_text_and_no_required_missing_material(self):
        data = paper_v2()
        understanding = data["knowledge"]["paper_understanding"]
        understanding["sources"][0]["kind"] = "other"
        self.invalid(data, "read full_text")
        understanding["sources"][0]["kind"] = "full_text"
        understanding["sources"].append({"source_id": "appendix", "kind": "supplement",
            "version": "unavailable-version", "status": "unavailable", "required": True,
            "path": None, "sha256": None})
        self.invalid(data, "required sources")
        understanding["coverage"]["status"] = "partial"
        self.validate(data)
        understanding["sources"][1]["required"] = False
        understanding["coverage"]["status"] = "complete"
        self.validate(data)

    def test_unavailable_source_must_not_claim_a_local_read(self):
        data = paper_v2()
        source = data["knowledge"]["paper_understanding"]["sources"][0]
        source["status"] = "unavailable"
        self.invalid(data, "path")
        source.update(path=None, sha256=None)
        data["knowledge"]["paper_understanding"]["coverage"]["status"] = "partial"
        self.invalid(data, "unavailable source")

    def test_navigation_and_reading_coverage_are_linked(self):
        for mutate in (
            lambda u: u["navigation"][0].update(source_id="missing"),
            lambda u: u["coverage"].update(read_anchor_ids=["missing"]),
            lambda u: u["coverage"].update(status="partial", unread_anchor_ids=["method"]),
            lambda u: u["navigation"].append(deepcopy(u["navigation"][0])),
            lambda u: u["sources"].append(deepcopy(u["sources"][0])),
        ):
            data = paper_v2()
            mutate(data["knowledge"]["paper_understanding"])
            self.invalid(data, "source_id|partition|duplicate")

    def test_all_local_reference_consumers_reject_wrong_anchor_source_pairs(self):
        for target in ("analysis", "trace", "pattern"):
            data = paper_v2()
            refs = (data["knowledge"]["paper_understanding"]["analysis"]["method"]["source_refs"]
                    if target == "analysis" else data["idea_trace"][0]["source_refs"]
                    if target == "trace" else data["knowledge"]["reasoning_patterns"][0]["source_refs"])
            refs[0]["source_id"] = "wrong-source"
            self.invalid(data, "does not resolve")

    def test_citing_unread_material_is_rejected(self):
        data = paper_v2()
        understanding = data["knowledge"]["paper_understanding"]
        understanding["sources"][0]["status"] = "partial"
        understanding["coverage"] = {"status": "partial", "read_anchor_ids": [], "unread_anchor_ids": ["method"]}
        self.invalid(data, "unread anchor")

    def test_trace_requires_reasoning_details_not_only_step_labels(self):
        for field in ("trace_id", "depends_on", "reasoning_operation", "assumptions", "alternatives", "testable_implication"):
            data = paper_v2()
            del data["idea_trace"][0][field]
            self.invalid(data, field)

    def test_trace_dependencies_can_be_non_linear_but_must_be_acyclic_and_resolve(self):
        data = paper_v2()
        node = deepcopy(data["idea_trace"][0])
        node.update(trace_id="premise")
        data["idea_trace"].append(node)
        data["idea_trace"][0]["depends_on"] = ["premise"]
        self.validate(data)  # Source order is not the order in which the authors discovered an idea.
        node["depends_on"] = ["design"]
        self.invalid(data, "cycle")
        node["depends_on"] = ["absent"]
        self.invalid(data, "unknown trace_id")
        node.update(trace_id="design", depends_on=[])
        self.invalid(data, "duplicate trace_id")

    def test_paper_pattern_references_cannot_borrow_another_papers_trace(self):
        for ref in ({"paper_id": "paper-b", "trace_id": "design"},
                    {"paper_id": "paper-a", "trace_id": "absent"}):
            data = paper_v2()
            data["knowledge"]["reasoning_patterns"][0]["trace_refs"] = [ref]
            self.invalid(data, "trace_refs")

    def test_empty_patterns_require_a_reason_and_duplicate_patterns_are_rejected(self):
        for stage, data in (("paper", paper_v2()), ("domain", domain_v2())):
            data["knowledge"]["reasoning_patterns"] = []
            self.invalid(data, "reasoning_patterns_reason", stage)
            data["knowledge"]["reasoning_patterns_reason"] = "Sources do not justify a transferable pattern"
            self.validate(data, stage)
        data = paper_v2()
        data["knowledge"]["reasoning_patterns"] *= 2
        self.invalid(data, "duplicate pattern_id")

    def test_domain_requires_explicit_source_ids_and_trace_gaps(self):
        data = domain_v2()
        pattern = data["knowledge"]["reasoning_patterns"][0]
        del pattern["trace_link_limitations"]
        self.invalid(data, "trace_link_limitations", "domain")
        pattern["trace_refs"] = [{"paper_id": "paper-a", "trace_id": "external-node"}]
        self.validate(data, "domain")  # Cross-file node existence is the coordinator's responsibility.
        for field in ("source_refs", "trace_refs"):
            changed = deepcopy(data)
            changed["knowledge"]["reasoning_patterns"][0][field][0]["paper_id"] = "unknown-paper"
            self.invalid(changed, "unknown source paper_id", "domain")

    def test_target_validation_is_separate_from_source_strategy_support(self):
        data = paper_v2()
        data["knowledge"]["reasoning_patterns"][0]["transfer_status"] = "validated_by_consensus"
        self.invalid(data, "unvalidated")


if __name__ == "__main__":
    unittest.main()
