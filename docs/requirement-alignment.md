# Project Requirement Alignment

This matrix uses `docs/requirement.md` as the authoritative project record. Scores are evidence-based: 0 means absent, 1 means planned, 2 means partial prototype, 3 means working and tested, and 4 means production-quality evidence.

## Baseline

| Requirement | Current evidence | Gap / next proof | Score |
| --- | --- | --- | ---: |
| Practical financial AI workflow | End-to-end Thai ID and medical-receipt review with extraction, deterministic checks, policy evidence, routing, audit, API, and UI | Validate with representative consented data before real operations use | 3 |
| Agents, tools, and automation | Bounded review workflow, typed actions, allowlisted tool registry, capped retries, fail-closed routing, and PII-safe audit trail | Add production persistence/integration only if justified by a real operations boundary | 3 |
| LLM application and structured output | Ollama vision extraction with versioned prompts, Pydantic schemas, request-time provider configuration, bounded correction retry, stable failures, and aggregate telemetry | Live accuracy remains network-dependent | 3 |
| Retrieval / RAG | Replaceable lexical retriever over versioned synthetic policies; cited explanations, no-evidence escalation, and recall/precision/grounding metrics | Compare embeddings only when broader data exposes a gap | 3 |
| Evaluations and guardrails | Machine-readable offline report covers structured fixture contracts, routing, false decisions, retrieval recall@3, citation correctness/precision, workflow success, grounding, human escalation, prompt injection, retries, fallbacks, latency, model calls, and cost | Expand live extraction benchmark when credentials are available | 3 |
| Reliability and user impact | Safe uploads/errors, extraction-grounded quality routing, timeouts, readiness, request IDs, aggregate metrics, CI definition, container setup, runbook, and review-evidence UI | Validate thresholds with representative consented documents and browser/container execution outside the restricted sandbox | 3 |
| Accuracy, hallucination, latency, cost | Versioned offline report explicitly labels deterministic mode and reports zero model calls/cost instead of implying live performance | Run and document credential-dependent extraction accuracy separately | 3 |
| Security, compliance, and trust | The branch tip replaces undocumented realistic assets with generated/watermarked fixtures and adds deterministic authority, bounded uploads, PII-safe logs/audits, prompt-injection containment, and trust boundaries | Obtain owner approval before any history purge; then add auth, durable policy versions, and external security review | 2 |
| Production-quality Python | Typed FastAPI service; 83 passing tests; validated configuration; Black-clean code; CI, container, health, and metrics artifacts | CI and container execution require an unrestricted environment | 3 |
| Ship and improve with evidence | Failure-driven loop log, verified local commits, CI definition, offline gates, runbook, and project brief | Run CI on GitHub and validate the live provider when credentials and network access are available | 3 |

## Baseline Verification — 2026-08-15

- `python -m pytest tests/unit -q`: **28 passed, 11 failed**. Most failures use the retired flat extraction schema; one legacy blur-fixture expectation contradicts the measured score.
- `python scripts/run_eval.py`: **failed at startup** because fixtures use the retired flat schema.
- `black --check app tests scripts`: **failed**; two files require formatting.
- `USE_MOCK_LLM=true python -m pytest tests/unit/test_main.py tests/unit/test_ui.py -q`: **8 passed**.
- Live Ollama evaluation was not run because it is credential-dependent and is not required for the offline baseline.

## Current Verified State

- `python -m pytest tests/unit -q`: **83 passed**. `python -m pytest -q`: **83 passed, 1 explicitly gated live test skipped**.
- `python scripts/run_eval.py`: **all declared routing, retrieval, workflow, citation, grounding, retry, and fallback gates passed**.
- `black --check app tests scripts`: **passed**.
- Generated ID and receipt fixtures are visibly marked as synthetic and have documented provenance. Blur and processed dimensions are advisory; structured extraction completeness and confidence drive quality routing.
- Workflow responses accurately audit image-quality, extraction, deterministic validation, retrieval, and action stages; unreadable inputs cannot claim validation ran, and no stage copies extracted PII.
- Policy retrieval is deliberately a deterministic lexical baseline; embeddings are deferred until an evaluation demonstrates a retrieval gap.
- Missing or contradictory policy effects fail closed to human review.
- Extraction prompts have explicit versions and provider clients are built from validated host/secret settings at request time rather than import time.
- `python scripts/run_eval.py` now emits ignored diagnostic JSON at `tests/evals/output/offline_metrics.json`; the current gate reports 100% fixture-contract schema validity and critical-field exact match, risk and document-quality routing accuracy, recall@3, workflow success, citation correctness/precision, grounded-answer rate, and human-escalation accuracy on the versioned synthetic matrix.

## Concrete Evidence Index

| Capability | Implementation | Verification / operating evidence |
| --- | --- | --- |
| Structured vision extraction | [`app/services/extractor.py`](../app/services/extractor.py), [`app/schemas.py`](../app/schemas.py) | [`tests/unit/test_extractor.py`](../tests/unit/test_extractor.py), [`tests/evals/run_evals.py`](../tests/evals/run_evals.py) |
| Deterministic KYC and claim guardrails | [`app/services/validator.py`](../app/services/validator.py) | [`tests/unit/test_validator.py`](../tests/unit/test_validator.py), [`scripts/run_eval.py`](../scripts/run_eval.py) |
| Bounded typed tool workflow | [`app/services/workflow.py`](../app/services/workflow.py) | [`tests/unit/test_workflow.py`](../tests/unit/test_workflow.py) |
| Grounded policy retrieval | [`app/services/retrieval.py`](../app/services/retrieval.py), [`data/policies/policies.json`](../data/policies/policies.json) | [`tests/unit/test_retrieval.py`](../tests/unit/test_retrieval.py), [`scripts/run_eval.py`](../scripts/run_eval.py) |
| Safe API and observability | [`app/main.py`](../app/main.py), [`app/config.py`](../app/config.py), [`app/observability.py`](../app/observability.py) | [`tests/unit/test_main.py`](../tests/unit/test_main.py), [`tests/unit/test_config.py`](../tests/unit/test_config.py), [`tests/unit/test_observability.py`](../tests/unit/test_observability.py) |
| Upload and image safety | [`app/services/image_processor.py`](../app/services/image_processor.py) | [`tests/unit/test_image_processor.py`](../tests/unit/test_image_processor.py) |
| Reviewer experience | [`app/static/index.html`](../app/static/index.html), [`app/static/app.js`](../app/static/app.js) | [`tests/unit/test_ui.py`](../tests/unit/test_ui.py), mock-flow verification in [`docs/loop-log.md`](loop-log.md) |
| Delivery and operations | [`Dockerfile`](../Dockerfile), [`compose.yaml`](../compose.yaml), [CI workflow](../.github/workflows/ci.yml) | [`docs/runbook.md`](runbook.md), [`docs/completion-audit.md`](completion-audit.md) |
| Synthetic-data provenance | [`data/mock_docs/README.md`](../data/mock_docs/README.md) | Watermarked samples plus [`tests/evals/ground_truth/synthetic_thai_id.json`](../tests/evals/ground_truth/synthetic_thai_id.json) |

## Requirement Coverage Notes

- **AI-native financial workflows:** The project demonstrates document intake, KYC, risk review, claims operations, and human escalation. Support, CRM, and product-intelligence workflows are acknowledged but intentionally not added without a real product need.
- **Agents, LLMs, retrieval, tool calling, evaluations, guardrails, and automation:** Each has executable evidence in `app/services/`, `data/policies/`, `tests/unit/`, and `scripts/run_eval.py`.
- **Real constraints:** Accuracy, false decisions, grounding, latency, retries, fallbacks, provider failures, upload safety, privacy, compliance authority, and cost labeling are tested or documented. Production scale is explicitly unclaimed.
- **Fixture privacy:** A visual audit found undocumented realistic identity and patient data in legacy samples. The working tree removes those assets and their duplicated benchmark; current replacements are generated, watermarked, fictional, and documented. The old blobs remain in Git history pending owner-authorized remediation.
- **Hands-on Python/JavaScript:** FastAPI/Pydantic services and the dependency-free review UI are implemented and tested. TypeScript is not used because the current UI does not justify a build toolchain.
- **Automation judgment:** Vision extraction and explanations use AI-facing boundaries; checksums, dates, arithmetic, status thresholds, tool authorization, and escalation remain deterministic or human-controlled.
- **Shipping and iteration:** `docs/loop-log.md` records failure-driven improvements, verification, and the consolidated verified commits created after Git write access became available.
- **Product/operations collaboration:** The repository makes product boundaries and questions explicit, but collaboration with real product, risk, compliance, or operations teams cannot be evidenced by a standalone portfolio repository.
- **Serious product bar:** CI, container, runbook, observability, security boundaries, UI, and evals move beyond a demo; durable storage, authentication, external telemetry, load testing, and real-data validation remain honest production gaps.

## Contextual Notes

- The requirement set is meant to be copy-paste runnable in Codex without editing the prompt structure.
- Communication should remain concise and evidence-based so the project can be reviewed as a side project.
- Any deployment, geography, or interview-process expectations from the original source are intentionally excluded from the active project scope.
