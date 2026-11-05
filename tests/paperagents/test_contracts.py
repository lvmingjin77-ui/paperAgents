"""Executable examples of valid and invalid research handoffs (no LLM needed)."""

from copy import deepcopy
from pathlib import Path
import json
import unittest

from paperagents.contracts import STAGES, artifact_schema, validate_artifact


_EXAMPLES: dict[str, dict] = {}


def artifacts() -> dict[str, dict]:
    """One accepted artifact per stage from a synthetic run, so examples always match the live contract."""
    if not _EXAMPLES:
        import tempfile
        from paperagents.workflow import Workflow, initialize_project
        from tests.paperagents.test_workflow import advance

        project = Path(tempfile.mkdtemp()) / "project"
        initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
        workflow = Workflow(project)
        advance(workflow)
        for task in workflow.state["tasks"].values():
            if task["status"] == "completed":
                data = workflow._artifact(task)
                for field in ("_asset", "source_paths"):  # coordinator-owned after acceptance
                    data.pop(field, None)
                _EXAMPLES.setdefault(task["stage"], data)
        _EXAMPLES["rebuttal"] = {
            "expert_id": "paper:p0", "revised_candidates": [], "withdrawn_idea_ids": [],
            "responses": [{"objection_id": "domain/1", "action": "rebut", "argument": "Section 3 rules it out.",
                           "evidence": ["p0#section-3"], "revised_idea_id": None}]}
        _EXAMPLES["recheck"] = {
            "expert_id": "domain", "new_reviews": [],
            "verdicts": [{"objection_id": "domain/1", "status": "resolved",
                          "reason": "The cited control excludes it.", "evidence": ["p0#section-3"]}]}
    return deepcopy(_EXAMPLES)


class ContractTests(unittest.TestCase):
    def assert_invalid(self, stage: str, data: dict, path: str | None = None) -> None:
        with self.assertRaises(ValueError) as error:
            validate_artifact(stage, data)
        if path:
            self.assertIn(path, str(error.exception))

    def test_all_handoffs_accept_evidence_records_and_extensions(self):
        examples = artifacts()
        self.assertEqual(set(STAGES), set(examples))
        for stage, data in examples.items():
            with self.subTest(stage=stage):
                data["producer_version"] = "test-version"
                self.assertIsNone(validate_artifact(stage, data))

    def test_every_stage_requires_its_documented_fields(self):
        for stage, data in artifacts().items():
            for field in artifact_schema(stage)["required"]:
                with self.subTest(stage=stage, field=field):
                    changed = deepcopy(data)
                    del changed[field]
                    self.assert_invalid(stage, changed, f"{stage}.{field}")

    def test_schema_is_json_serializable_and_does_not_leak_mutations(self):
        for stage in STAGES:
            schema = artifact_schema(stage)
            self.assertEqual(json.loads(json.dumps(schema)), schema)
            schema["properties"].clear()
            self.assertTrue(artifact_schema(stage)["properties"])

    def test_unknown_stage_and_wrong_root_are_value_errors(self):
        for stage in ("made_up", "", None, []):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                artifact_schema(stage)
        self.assert_invalid("scope", [])

    def test_partial_corpus_can_report_unavailable_full_text(self):
        for path in (None, ""):
            data = artifacts()["corpus"]
            data["papers"][0]["full_text_path"] = path
            data["coverage"]["status"] = "partial"
            data["missing_sources"] = ["Paper A appendix is unavailable"]
            self.assertIsNone(validate_artifact("corpus", data))
            data["coverage"]["status"] = "complete"
            self.assert_invalid("corpus", data, "full_text_path")

    def test_complete_corpus_must_not_hide_missing_sources_or_be_empty(self):
        data = artifacts()["corpus"]
        data["missing_sources"] = ["Unretrieved relevant paper"]
        self.assert_invalid("corpus", data, "missing_sources")
        data["missing_sources"] = []
        data["papers"] = []
        self.assert_invalid("corpus", data, "papers")
        data["coverage"]["status"] = "insufficient"
        self.assertIsNone(validate_artifact("corpus", data))

    def test_coverage_status_is_explicit(self):
        data = artifacts()["corpus"]
        data["coverage"] = {"comment": "Looks comprehensive"}
        self.assert_invalid("corpus", data, "coverage.status")

    def test_complete_corpus_requires_search_records(self):
        data = artifacts()["corpus"]
        data["search_log"] = []
        self.assert_invalid("corpus", data, "search_log")
        data["coverage"]["status"] = "partial"
        self.assertIsNone(validate_artifact("corpus", data))

    def test_scope_requires_a_venue_and_paper_experts_require_an_idea_trace(self):
        data = artifacts()["scope"]
        data["venues"] = []
        self.assert_invalid("scope", data, "venues")
        data = artifacts()["paper"]
        data["idea_trace"] = []
        self.assert_invalid("paper", data, "idea_trace")

    def test_core_papers_must_be_distinct_and_bounded(self):
        # The exact configured count is checked by the coordinator against research.core_papers.
        for ids in ([], ["a", "b", "c", "d", "e", "f"], ["a", "a", "b"]):
            with self.subTest(ids=ids):
                data = artifacts()["selection"]
                data["core_paper_ids"] = ids
                self.assert_invalid("selection", data, "core_paper_ids")

    def test_temporary_expert_without_sources_must_disclose_material_gap(self):
        data = artifacts()["selection"]
        consultant = {"expert_id": "statistics", "specialty": "Statistics",
                      "reason": "Check variance estimates", "source_paper_ids": []}
        data["temporary_experts"] = [consultant]
        self.assert_invalid("selection", data, "material_gaps")
        consultant["material_gaps"] = []
        self.assert_invalid("selection", data, "material_gaps")
        consultant["material_gaps"] = ["Statistical references still need retrieval"]
        self.assertIsNone(validate_artifact("selection", data))
        consultant["source_paper_ids"] = ["stats-paper"]
        del consultant["material_gaps"]
        self.assertIsNone(validate_artifact("selection", data))

    def test_idea_trace_does_not_treat_inferred_reasoning_as_author_statement(self):
        for basis in ("author_stated", "reconstructed", "unknown"):
            for stage in ("paper", "reading"):
                with self.subTest(basis=basis, stage=stage):
                    data = artifacts()[stage]
                    trace = data["idea_trace"]
                    trace[0].update(basis=basis, source_refs=[])
                    if basis == "unknown":
                        self.assertIsNone(validate_artifact(stage, data))
                    else:
                        self.assert_invalid(stage, data, "source_refs")
        data = artifacts()["paper"]
        data["idea_trace"][0]["basis"] = "proven_author_intention"
        self.assert_invalid("paper", data, "basis")

    def test_code_capability_status_requires_actual_verification_record(self):
        for status in ("documented", "wrapped", "tested", "reproduced"):
            with self.subTest(status=status):
                data = artifacts()["paper"]
                tool = {"name": "Method runner", "status": status, "verification_evidence": []}
                data["code_tools"] = [tool]
                data["source_paths"] = ["tools/method.py"]
                if status in ("tested", "reproduced"):
                    self.assert_invalid("paper", data, "verification_evidence")
                else:
                    self.assertIsNone(validate_artifact("paper", data))
                tool["verification_evidence"] = [{"run_id": "test-run", "result_path": "test.json"}]
                self.assertIsNone(validate_artifact("paper", data))

    def test_non_documented_tools_require_files_for_coordinator_snapshot(self):
        for status in ("wrapped", "tested", "reproduced"):
            with self.subTest(status=status):
                data = artifacts()["paper"]
                data["code_tools"] = [
                    {"name": "Background mapping", "status": "documented", "verification_evidence": []},
                    {"name": "Callable method", "status": status, "verification_evidence": ["run-1"]},
                ]
                self.assert_invalid("paper", data, "source_paths")
                data["source_paths"] = []
                self.assert_invalid("paper", data, "source_paths")
                data["source_paths"] = [""]
                self.assert_invalid("paper", data, "source_paths[0]")
                data["source_paths"] = ["tools/method.py", "tools/configs"]
                self.assertIsNone(validate_artifact("paper", data))
        data = artifacts()["paper"]
        data["code_tools"] = [{"name": "Mapping only", "status": "documented", "verification_evidence": []}]
        self.assertIsNone(validate_artifact("paper", data))
        data["source_paths"] = []
        self.assertIsNone(validate_artifact("paper", data))

    def test_paper_without_code_remains_valid_with_disclosed_limitation(self):
        data = artifacts()["paper"]
        self.assertIsNone(validate_artifact("paper", data))
        data["limitations"] = []
        self.assert_invalid("paper", data, "limitations")

    def test_review_acceptance_cannot_hide_failed_or_unknown_checks(self):
        for stage in ("expert_review", "proposal_review"):
            for verdict in ("fail", "unknown"):
                with self.subTest(stage=stage, verdict=verdict):
                    data = artifacts()[stage]
                    data["checks"][0]["verdict"] = verdict
                    self.assert_invalid(stage, data, "verdict")
                    data["accepted"] = False
                    self.assertIsNone(validate_artifact(stage, data))
            data = artifacts()[stage]
            data["checks"] = []
            self.assert_invalid(stage, data, "checks")

    def test_check_shape_and_boolean_acceptance_are_required(self):
        data = artifacts()["expert_review"]
        data["checks"] = ["pass"]
        self.assert_invalid("expert_review", data, "checks[0]")
        for value in (1, "true"):
            data = artifacts()["expert_review"]
            data["accepted"] = value
            self.assert_invalid("expert_review", data, "accepted")
        data = artifacts()["expert_review"]
        del data["checks"][0]["evidence"]
        self.assert_invalid("expert_review", data, "evidence")

    def test_accepted_review_requires_evidence_for_every_passing_check(self):
        for stage in ("expert_review", "proposal_review"):
            with self.subTest(stage=stage):
                data = artifacts()[stage]
                data["checks"][0]["evidence"] = []
                self.assert_invalid(stage, data, "evidence")
                data["accepted"] = False
                self.assertIsNone(validate_artifact(stage, data))

    def test_accepted_proposal_review_cannot_retain_blocking_issue(self):
        data = artifacts()["proposal_review"]
        data["blocking_issues"] = ["Missing baseline evaluation"]
        self.assert_invalid("proposal_review", data, "blocking_issues")

    def test_ready_proposal_requires_executable_plan_and_evaluation(self):
        for field, value in (("implementation_plan", []), ("evaluation", {}),
                             ("implementation_plan", [{"step": "Not a v3 plan string"}]),
                             ("source_refs", []), ("title", "")):
            with self.subTest(field=field):
                data = artifacts()["synthesis"]
                data["proposal"][field] = value
                self.assert_invalid("synthesis", data, field)
        data = artifacts()["synthesis"]
        data["selected_idea_id"] = None
        self.assert_invalid("synthesis", data, "selected_idea_id")

    def test_unready_synthesis_can_honestly_report_no_proposal(self):
        for decision in ("needs_evidence", "no_viable_idea"):
            data = artifacts()["synthesis"]
            data.update(decision=decision, selected_idea_id=None, proposal={}, next_action="gather_materials")
            data["unresolved_questions"] = [{"question": "Is the baseline valid?", "blocking": True}]
            self.assertIsNone(validate_artifact("synthesis", data))

    def test_ready_synthesis_rejects_explicit_blockers_without_text_heuristics(self):
        data = artifacts()["synthesis"]
        data["unresolved_questions"] = [{"question": "Follow-up", "blocking": True}]
        self.assert_invalid("synthesis", data, "unresolved_questions")
        data["unresolved_questions"][0]["blocking"] = False
        self.assertIsNone(validate_artifact("synthesis", data))
        data["unresolved_questions"] = ["This text requires scientific review, not keyword matching."]
        self.assertIsNone(validate_artifact("synthesis", data))

    def test_novelty_states_are_explicit_and_empty_candidate_sets_are_allowed(self):
        for status in ("distinct", "overlap", "uncertain"):
            data = artifacts()["novelty"]
            data["reviews"][0]["status"] = status
            self.assertIsNone(validate_artifact("novelty", data))
        data["reviews"][0]["status"] = "novelty_score_9"
        self.assert_invalid("novelty", data, "status")
        self.assertIsNone(validate_artifact("hypothesis", {"expert_id": "domain", "candidates": []}))

    def test_json_values_are_required_even_in_extensible_knowledge(self):
        for bad in ({"set"}, float("nan"), float("inf"), {1: "non-string key"}):
            with self.subTest(value=repr(bad)):
                data = artifacts()["domain"]
                data["knowledge"]["extra"] = bad
                self.assert_invalid("domain", data, "domain.knowledge.extra")
        data = artifacts()["corpus"]
        data["papers"][0]["year"] = True
        self.assert_invalid("corpus", data, "year")


if __name__ == "__main__":
    unittest.main()
