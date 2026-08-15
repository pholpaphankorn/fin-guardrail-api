# Engineering Loop Log

## Loop 0 — Establish an evidence-based baseline

- **Problem:** The repository had no durable mapping from the project requirement to implementation evidence, and the health of tests and evaluations was uncertain.
- **Success criterion:** Record the requirement gaps and results of the current unit, evaluation, formatting, and mock API checks without changing product behavior.
- **Change:** Added the alignment matrix, baseline results, and this progress log. Preserved `docs/loop-engineering-goal.md` and `docs/requirement.md` as user-provided source documents.
- **Verification:**
  - `python -m pytest tests/unit -q` — 28 passed, 11 failed (documented baseline)
  - `python scripts/run_eval.py` — failed on legacy flat-schema fixtures (documented baseline)
  - `black --check app tests scripts` — two files require formatting (documented baseline)
  - `USE_MOCK_LLM=true python -m pytest tests/unit/test_main.py tests/unit/test_ui.py -q` — 8 passed
  - `git diff --check` — passed
- **Next remediation:** Align fixtures and deterministic evaluation data with the confidence-wrapped extraction schema, then investigate the mislabeled blur sample.
- **Planned commit:** `chore: define applied AI refinement baseline`

## Loop 1 — Restore schema and evaluation correctness

- **Problem:** Tests and the deterministic evaluation runner constructed a retired flat extraction schema. A visually sharp medical receipt was mislabeled as blurry despite a focus score of 3424.62 against a threshold of 50.
- **Success criterion:** The complete unit suite, deterministic routing evaluation, formatter, and whitespace checks pass without weakening production schemas or validation rules.
- **Change:** Added complete confidence-wrapped test/evaluation builders, updated extractor assertions to access typed field values, corrected the receipt fixture classification, and applied Black formatting.
- **Verification:**
  - `python -m pytest tests/unit -q` — 39 passed
  - `python scripts/run_eval.py` — 5/5 passed
  - `black --check app tests scripts` — passed
  - `git diff --check` — passed
- **Next remediation:** Add the bounded typed review workflow, tool authorization, safe audit events, and workflow tests.
- **Planned commit:** `change: align validation suite with extraction schema`
- **Commit status:** Included in verified product commit `5a9c592` after Git write access became available.

## Loop 2 — Add a bounded, auditable review workflow

- **Problem:** The API ended at a risk status and did not demonstrate tool orchestration, bounded retries, authorization, or an operations action.
- **Success criterion:** Both document endpoints return a typed workflow decision; tests prove allowlisting, capped attempts, PII-safe audit events, fail-closed behavior, and deterministic routing authority.
- **Change:** Added a workflow state machine, tool registry, typed actions/audit models, API integration, and focused workflow/API tests.
- **Verification:**
  - `python -m pytest tests/unit -q` — 48 passed at loop completion
  - `python scripts/run_eval.py` — 5/5 passed
  - `black --check app tests scripts` — passed
  - `git diff --check` — passed
- **Next remediation:** Ground workflow explanations in retrieved synthetic policy evidence.
- **Planned commit:** `change: add bounded document review workflow`
- **Commit status:** Included in verified product commit `5a9c592` after Git write access became available.

## Loop 3 — Ground workflow explanations in policy evidence

- **Problem:** Workflow explanations had no retrieval evidence or citations, so they could not demonstrate grounded RAG behavior.
- **Success criterion:** A replaceable offline retriever returns document-appropriate policies, explanations cite them, missing evidence escalates, and prompt-injection text cannot enter retrieval queries or audit output.
- **Change:** Added a synthetic policy corpus, lexical retrieval baseline, citation schemas, retrieval workflow tool, grounded templates, no-evidence escalation, and focused retrieval/adversarial tests.
- **Verification:**
  - `python -m pytest tests/unit -q` — 56 passed
  - `python scripts/run_eval.py` — 5/5 passed
  - `black --check app tests scripts` — passed
  - `git diff --check` — passed
- **Next remediation:** Produce machine-readable offline evaluation reports for routing, retrieval, workflow completion, latency, retries, fallbacks, and groundedness.
- **Planned commit:** `change: ground review workflow in policy retrieval`
- **Commit status:** Included in verified product commit `5a9c592` after Git write access became available.

## Loop 4 — Turn offline evaluation into a measurable regression gate

- **Problem:** The deterministic script printed only routing accuracy and could not substantiate retrieval, grounding, tool reliability, latency, or cost claims.
- **Success criterion:** One offline command emits a machine-readable report and exits nonzero unless all declared safety thresholds pass.
- **Change:** Rebuilt `scripts/run_eval.py` with six routing cases, six retrieval cases, three workflow cases, prompt-injection containment, retry/fallback injection, percentile latency, and explicit zero live-model usage. Added citation precision after the first report exposed irrelevant extra citations, then tightened retrieval queries to stable flag codes.
- **Verification:**
  - `python scripts/run_eval.py` — routing 6/6; recall@3 100%; workflow success 100%; citation correctness/precision 100%; grounded answers 100%; unsupported claims 0; retries 2; fallbacks 1; model calls 0
  - `python -m pytest tests/unit -q` — 56 passed
  - `black --check app tests scripts` — passed
  - `git diff --check` — passed
- **Next remediation:** Harden configuration, uploads, provider timeouts, readiness, and PII-safe request observability.
- **Planned commit:** `test: add offline AI workflow evaluation report`
- **Commit status:** Committed as `d40a20b test: add offline AI workflow evaluation gate`.

## Loop 5 — Harden the API and delivery path

- **Problem:** Uploads, provider calls, readiness, runtime diagnostics, CI, and deployment behavior lacked explicit operational boundaries.
- **Success criterion:** Unsafe inputs and provider failures return stable responses; runtime signals are PII-free; CI/container/runbook artifacts are valid; offline gates remain green.
- **Change:** Added validated settings, 10 MB/MIME/pixel upload limits, live-provider readiness, provider timeouts and safe errors, request IDs, structured request logs, aggregate metrics, explicit live-test opt-in, current tested dependency pins, CI, a non-root read-only container setup, Compose, `.env.example`, and an operations runbook.
- **Verification:**
  - `python -m pytest -q` — 67 passed, 2 live tests skipped
  - `python scripts/run_eval.py` — all thresholds passed
  - `ruby -e "require 'yaml'; ..."` — CI and Compose YAML parsed
  - `docker compose --env-file .env.example config --quiet` — passed
  - `black --check app tests scripts` and `git diff --check` — passed
- **External verification:** Docker build could not access the sandboxed daemon. Live extraction reached the provider boundary but network access was blocked; no accuracy claim was made.
- **Next remediation:** Present workflow actions, citations, and audit evidence in the review UI and finish portfolio documentation.
- **Planned commits:** `change: harden document API operations`; `chore: add CI and container delivery path`
- **Commit status:** API behavior is included in `5a9c592`; delivery artifacts are committed as `884db4a`.

## Loop 6 — Make evidence visible and interview-ready

- **Problem:** The UI showed extracted fields and flags but hid the agent workflow, retrieved policy evidence, and tool history; project documentation described an earlier architecture.
- **Success criterion:** The review page exposes safe workflow evidence, documentation states measured results and limitations accurately, and mock sample flows return citations and audit events.
- **Change:** Added workflow action, grounded explanation, policy citation, and tool-audit panels; rewrote the README; added the project brief; refreshed contributor guidance and requirement-alignment coverage.
- **Verification:**
  - `node --check app/static/app.js` — passed
  - UI/API contract tests are included in the 67-test green suite
  - Real sample uploads through the ASGI app returned grounded workflow output for both document types
  - `black --check app tests scripts` and `git diff --check` — passed
- **External verification:** Interactive browser QA was unavailable because the browser runtime file is missing and local listening sockets are forbidden. This is recorded as unverified, not passed.
- **Next remediation:** Run the final requirement-by-requirement audit and publish the documentation commit locally.
- **Planned commits:** `change: show policy evidence in review UI`; `chore: document applied AI system evidence`
- **Commit status:** UI behavior is included in `5a9c592`; the documentation commit remains planned until this log is finalized.

## Loop 7 — Make pipeline and provider evidence traceable

- **Problem:** Workflow audits omitted preprocessing tools and could incorrectly imply validation ran after unreadable extraction; retrieval did not reject contradictory policy effects; extraction prompts and provider construction were not versioned or fully runtime-configurable.
- **Success criterion:** Audit events match the stages that actually ran, missing/conflicting policy evidence fails closed, offline evaluation includes structured-output and escalation metrics, and provider calls use validated request-time settings with stable prompt versions.
- **Change:** Added typed image-quality/extraction workflow tools, accurate early-exit audits, policy-effect schemas and conflict detection, fixture-contract and human-escalation evaluation metrics, request-time Ollama client construction, extraction prompt versions, and focused regression tests.
- **Verification:**
  - `python -m pytest tests/unit -q` — 70 passed
  - `python -m pytest -q` — 70 passed, 2 explicitly gated live tests skipped
  - `python scripts/run_eval.py` — all structured-output, routing, retrieval, workflow, grounding, escalation, retry, fallback, latency, and cost-labeling gates passed
  - Bundled Thai ID and receipt uploads through ASGI mock mode returned HTTP 200 with request IDs, citations, and five-stage audit trails
  - `black --check app tests scripts`, `node --check app/static/app.js`, CI/Compose YAML parsing, `docker compose --env-file .env.example config --quiet`, and `git diff --check` — passed
- **External verification:** Live provider accuracy, Docker execution, browser interaction, and CI execution remain unavailable in the restricted environment; none is reported as passed.
- **Planned commit:** `change: make workflow and provider evidence fail closed`
- **Commit status:** Product behavior is included in `5a9c592`; evaluation coverage is included in `d40a20b`.

## Loop 8 — Remove undocumented identity and medical data

- **Problem:** Visual inspection proved the tracked sample set included realistic full identity details and patient identifiers with no synthetic-data provenance; one identity image and its PII-rich ground truth were duplicated in the live benchmark.
- **Success criterion:** No undocumented personal document remains in the current working tree, replacement samples are unmistakably fictional and traceable, the live benchmark uses fictional ground truth, and deterministic rules reject the placeholder identity number.
- **Change:** Removed five legacy sample images plus the duplicated benchmark image/ground truth; generated a watermarked fictional Thai ID and medical receipt using the built-in image tool; added provenance documentation and fictional live-eval ground truth; updated UI, tests, mock outputs, and demo paths; rejected repeated-digit ID placeholders; and enforced agreement between filename, declared MIME, and binary signature.
- **Verification:**
  - `python -m pytest tests/unit -q` — 73 passed
  - `python -m pytest -q` — 73 passed, 1 explicitly gated live test skipped
  - `python scripts/run_eval.py` — all declared gates passed
  - Both generated fixtures returned HTTP 200 with request IDs, grounded citations, and five-stage audit trails through ASGI mock mode
  - `black --check app tests scripts`, `node --check app/static/app.js`, CI/Compose YAML parsing, `docker compose --env-file .env.example config --quiet`, and `git diff --check` — passed
- **Recovery:** Removed files were copied to `/tmp/fin-guardrail-unsafe-fixtures` for temporary recovery during this session; they must not be recommitted.
- **Planned commit:** `change: replace sensitive samples with synthetic fixtures`
- **Commit status:** Committed as part of `5a9c592`; the branch tip contains only the documented synthetic replacements.

## Commit reconciliation

Git metadata was read-only while Loops 0–8 were implemented and verified, so the changes accumulated before commit access was restored. They were grouped by cohesive review boundary rather than split into artificial after-the-fact commits: `5a9c592` contains the product, safety, UI, and synthetic-fixture work; `d40a20b` contains the offline evaluation gate; `884db4a` contains CI and container delivery. Repository guidance, alignment evidence, the runbook, and this log use the planned documentation commit `chore: document applied AI system evidence`.

## Loop 9 — Simplify the requirement document name

- **Problem:** The authoritative requirement filename was unnecessarily long and appeared in several guidance documents.
- **Success criterion:** Rename it to `docs/requirement.md`, update every repository reference, and leave no stale path.
- **Change:** Renamed the document and updated the goal, alignment matrix, completion audit, and loop log references.
- **Verification:** Repository search found no remaining reference to the old filename; `git diff --check` passed.
- **Planned commit:** `chore: rename requirement document`

## Loop 10 — Link the requirement source

- **Problem:** The local requirement record did not identify its public source.
- **Success criterion:** Add a readable source link without changing the captured requirement content.
- **Change:** Added the source reference at the top of `docs/requirement.md`.
- **Verification:** Confirmed the Markdown link and `git diff --check` passed.
- **Planned commit:** `chore: link requirement source`

## Loop 11 — Ground document legibility in extraction evidence

- **Problem:** A stashed legibility heuristic conflicted with the verified branch and produced unsafe behavior: pristine fixtures scored below its threshold, severe downscaling increased its score, and random noise passed. It also removed upload protections.
- **Success criterion:** Preserve every upload defense; expose PII-free quality evidence; use structured extraction completeness and confidence as the primary routing signal; treat blur and dimensions as advisory; and escalate uncertainty without an automated irreversible decision.
- **Change:** Retained the verified conflict side, added typed image/extraction quality reports, routed insufficient evidence to resubmission and uncertain evidence to human review, displayed quality evidence in the UI, grounded the new flag in policy, and retained the original stash for recovery.
- **Verification:** `python -m pytest -q` passed with 83 tests and one explicitly gated live test skipped; the offline evaluation passed all thresholds, including 6/6 document-quality routes, 7/7 retrieval cases, and 4/4 workflow cases; Black, JavaScript syntax, YAML, Compose configuration, and whitespace checks passed. Both synthetic documents returned HTTP 200 with quality evidence in mock mode; the synthetic ID remained deterministically rejected for its placeholder number, while the receipt remained approved.
- **Planned commit:** `change: ground legibility in extraction evidence`
