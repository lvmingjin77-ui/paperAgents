# PaperAgents artifact contracts

`paperagents.contracts` provides two standard-library-only APIs for Python 3.11+:

```python
from paperagents.contracts import artifact_schema, validate_artifact

schema = artifact_schema("hypothesis")  # JSON Schema draft 2020-12 for the worker
validate_artifact("hypothesis", worker_output)  # None, or ValueError with a field path
```

There is one current contract; no version arguments or legacy branches remain:

```python
schema = artifact_schema("paper")
validate_artifact("paper", worker_output)
```

It requires `knowledge.paper_understanding` for paper artifacts and structured
`knowledge.reasoning_patterns` for both paper and domain artifacts (an empty list
requires a reason); domain artifacts also carry `knowledge.landscape`. It validates
source/anchor references, reading coverage, seven analysis dimensions, unique
trace IDs, acyclic dependencies, and strategy links. The coordinator additionally
checks actual file hashes, the assigned full-text version, and that every paper the
landscape cites has a reading record. Proposal reviews carry six-dimensional scores
and a `decision_assessment`. Detailed structures are in
[paper-expert-capabilities.md](paper-expert-capabilities.md) and
[ideation-discussion.md](ideation-discussion.md).

Runs created under an older workflow contract are refused (their files are kept);
start a fresh run with `paperagents run <project> --new`.

Schemas and validation share one definition. Each schema call returns a separate
copy; callers may annotate it without changing subsequent validation. Additional
fields are generally allowed for provenance and future extensions; the review's
`dimensions` object contains exactly the six named dimensions. All values must
be JSON values, including inside extensible knowledge records.

## Validation boundary

A ready synthesis binds
`candidate_ref` to the frozen candidate digest and preserves its problem,
hypothesis, mechanism, assumptions and falsification fields. Distinct novelty
requires structured real-search records, including honest zero results. Accepted
expert/proposal reviews cover the named criteria exactly once; a single format
check cannot stand in for scientific acceptance. Detailed worker fields are in
[the runtime contract](../../skills/references/runtime-contract.md).

Passing a contract only establishes artifact structure and explicit state
consistency. It does **not** establish scientific truth, complete literature
coverage, novelty, working code, or a valid experimental result. The independent
review must verify that full-text files exist and are readable, source locators
resolve, source passages support the associated statements, and the expert's
interpretation respects the source. The orchestrator checks IDs and dependencies
across files, including the selected papers, experts, candidates, and reviews.

A path or a source reference is a claim of evidence availability, not a verified
fact. A `ready` synthesis must still pass the independent proposal review.

## Shared record shapes

- A reference/evidence item is a nonempty string locator or a nonempty JSON object.
  Prefer structured records carrying a source ID, location, and relevant excerpt.
- `knowledge` is a nonempty object. Preserve source facts, author-stated reasoning,
  system inferences, and unknowns separately; this module does not infer those
  categories from natural language or enforce a particular knowledge layout.
- An `idea_trace` item has `step` (positive integer or nonempty string), `statement`,
  `basis`, and `source_refs`. `basis` is `author_stated`, `reconstructed`, or
  `unknown`. The first two require at least one source reference. A reconstruction
  remains a reconstruction even when cited; it must not be presented as the
  authors' actual intent. Unknown reasoning may have an empty reference list.
- A `code_tools` item has `name`, `status`, and `verification_evidence` (a list).
  Status is `documented`, `wrapped`, `tested`, or `reproduced`. Only `tested` and
  `reproduced` require nonempty verification evidence. Packaging a command does
  not establish that it runs or reproduces results. Papers with no executable
  method remain usable: supply `code_tools: []` and disclose the limitation.
- A paper artifact may include `source_paths`, a list of nonempty local file or
  directory paths. If any tool is `wrapped`, `tested`, or `reproduced`, this list
  is required and nonempty so the coordinator can freeze its actual files.
  `documented` tools do not require executable sources. The coordinator checks
  path existence, copies sources, and records their content hashes; the schema
  only checks the declared paths. Workers must not supply `_asset`: it is
  coordinator-generated snapshot metadata, not a research claim or worker field.
- A review check has `check`, `evidence` (a list), and
  `verdict: pass | fail | unknown`. Independent review decides the verdict;
  the contract merely verifies its shape and consistency with acceptance.

## Stages and required fields

| Stage | Required fields and structural constraints |
| --- | --- |
| `scope` | `direction`, nonempty `venues`, nonempty `queries`, nonempty `inclusion_criteria`. The three latter fields are string lists. |
| `corpus` | `papers`, `coverage`, `search_log`, `missing_sources`. Each paper has `paper_id`, `title`, positive integer `year`, `venue`, `source_url`, `full_text_path`, `idea_trace`. |
| `domain` | `expert_id: domain`, nonempty `knowledge`, nonempty `source_paper_ids`, `limitations`. |
| `selection` | Exactly three distinct `core_paper_ids`, nonempty `selection_reasons` object, `temporary_experts` list. |
| `paper` | `expert_id`, `paper_id`, nonempty `knowledge`, nonempty `idea_trace`, `code_tools`, `limitations`. No code tools requires a nonempty limitations list. Optional `source_paths` is a string list, required and nonempty if any tool is wrapped, tested, or reproduced. |
| `consultant` | `expert_id`, `specialty`, nonempty `knowledge`, `source_refs`, `limitations`. This is an optional specialist in addition to the domain expert and three core paper experts. |
| `expert_review` | `expert_id`, boolean `accepted`, `checks`, `limitations`. Acceptance requires at least one check, all with verdict `pass` and nonempty evidence. |
| `hypothesis` | `expert_id`, `candidates`. Each candidate has `idea_id`, `title`, `problem`, `hypothesis`, `mechanism`, `assumptions`, `nearest_work`, `falsification`, `experiment_plan`, nonempty `source_refs`. Falsification and experiment plan can be nonempty text or structured objects. Empty candidates explicitly permit producing no viable idea. |
| `challenge` | `expert_id`, `reviews`. Each review has `idea_id`, `claims`, `required_evidence` lists. |
| `novelty` | `reviews`. Each item has `idea_id`, `status: distinct | overlap | uncertain`, `nearest_work`, `search_log`, `reason`. Status describes a conclusion within the documented search, not universal proof of novelty. |
| `synthesis` | `decision: ready | needs_evidence | no_viable_idea`, `selected_idea_id`, `proposal`, `alternatives`, `unresolved_questions`. See the readiness rules below. |
| `proposal_review` | Boolean `accepted`, `checks`, `blocking_issues`. Acceptance requires nonempty all-pass checks, evidence for each check, and no blocking issues. Review v2 additionally requires `candidate_scores` and `proposal_score`, described below. |

`coverage.status` must be `complete`, `partial`, or `insufficient`. A `complete`
corpus must contain at least one paper, every listed paper must have a nonempty
full-text path and a nonempty idea trace, `search_log` must be nonempty, and
`missing_sources` must be empty. Partial or insufficient
corpora may use `null` or an empty path for missing full text and must describe
the gaps honestly. This structural rule cannot determine whether the search
actually covers the domain, whether all relevant papers were listed, or whether
the claimed local files exist.

Each temporary expert has `expert_id`, `specialty`, `reason`, and
`source_paper_ids`. If the source-paper list is empty, a nonempty `material_gaps`
list is required. With sources, `material_gaps` is optional. This makes missing
materials explicit without trying to interpret a prose reason with keywords.

For a `ready` synthesis, `selected_idea_id` must be nonempty and `proposal` must
include `title`, `problem`, `hypothesis`, a nonempty `implementation_plan` string list,
a nonempty `evaluation` object, and nonempty `source_refs`. Other decisions allow
`selected_idea_id: null` and `proposal: {}`. A ready artifact cannot contain an
unresolved-question object with `blocking: true`; plain-text questions and other
objects still require scientific review to determine whether they block
readiness. The validator does not guess severity from wording.

## Six-dimensional review scores

Review v2 scores every current candidate and the final synthesized proposal as
separate objects. `candidate_scores` is a nonempty list of records containing
`idea_id`, `candidate_hash`, and `dimensions`. `proposal_score` contains
`proposal_hash` and `dimensions`. The coordinator supplies
`context.review_targets` with `candidates` (each candidate's ID and hash),
`selected_idea_id`, and `proposal_hash`; the reviewer copies these identities.
Submission checks complete, unique candidate coverage and matching hashes.
Hashes identify the scored versions; they do not establish semantic equivalence
between a candidate and the synthesized proposal or establish scientific truth.

Each `dimensions` object has exactly these six keys:

| Key | Display label |
| --- | --- |
| `problem_value` | 问题价值 |
| `novelty` | 新颖性与研究增量 |
| `mechanism_soundness` | 机制与逻辑合理性 |
| `evidence_quality` | 已有依据的可靠性 |
| `experimental_discriminability` | 实验判别力 |
| `feasibility` | 实施可行性 |

Every dimension includes `status`, `score`, `rationale`, and an `evidence` list.
For `status: scored`, the score is an integer from 1 through 5 and evidence is
nonempty. For `status: unknown`, the score is `null` and the rationale explains
the missing basis; any available evidence may still be included. Reasons are
required in both cases. See the shared [scoring rubric](../../skills/references/review-scoring.md)
for the 1/3/5 anchors and how to handle intermediate scores and uncertainties.

Scores are displayed without a weighted total, aggregate ranking, or automatic
acceptance threshold. High scores cannot override blocking issues. A low score
or unknown dimension does not itself reject a proposal: its implication for
admission must be recorded in `checks` and `blocking_issues`. In particular,
unmeasured effectiveness is not a reason to penalize an otherwise testable idea.
The existing acceptance checks remain separate from these comparative scores.

`paperagents review <project>` renders the current review as a Chinese Markdown
comparison, followed by per-dimension reasons, evidence, and the admission
decision. Rejected reviews are visible too. A missing review or a historical
review without scores is reported explicitly; no values are synthesized for it.

## Verification

The contract tests run without a model, GPU, network, or external Python package:

```bash
python -m unittest discover -s tests/paperagents -p test_contracts.py
```

The tests cover complete and incomplete literature acquisition, source-grounded
idea traces, optional executable methods, specialist material gaps, independent
review acceptance, and honest non-ready synthesis states.
