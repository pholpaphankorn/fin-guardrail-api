# Project Brief

## Summary

Fin-Guardrail turns Thai KYC and medical-claim document review into a bounded AI-assisted workflow. A vision model performs typed extraction, deterministic Python owns high-stakes checks, retrieval supplies synthetic policy evidence, and an allowlisted workflow routes approval, rejection, resubmission, or human review with a PII-safe audit trail.

## Engineering Decisions

1. **AI does not own irreversible decisions.** OCR and explanation benefit from a model; checksums, expiry, arithmetic, thresholds, tool authorization, and escalation are deterministic.
2. **The agent is bounded.** It is a state machine with typed actions, an allowlist, one configurable retry budget capped at three, and fail-closed behavior-not an open-ended autonomous loop.
3. **RAG started with a baseline.** A lexical retriever is transparent, fast, offline, and sufficient for the current corpus. Embeddings should be introduced only after recall/precision cases expose a gap.
4. **Evidence is explicit.** Explanations cite policy IDs. If retrieval returns no support, the system says so and routes to a person.
5. **Privacy shapes observability.** Request IDs and aggregate counters support debugging, while bodies, extracted fields, names, ID numbers, and medical details never enter logs or workflow audit events.
6. **Provider behavior is traceable.** Runtime host and secret settings create each provider client, and stable extraction prompt versions are exposed without revealing credentials.
7. **Legibility is evidence-based.** Pixel heuristics are noisy supporting signals. Structured field completeness and confidence determine whether the workflow continues, requests resubmission, or creates human review.

## Iteration History

- Baseline: 28 unit tests passed and 11 failed because tests and evaluations used a retired flat schema.
- Correction: fixtures now build the required confidence-wrapped model; the unit suite is green.
- Image-quality investigation: a legacy receipt labeled blurry measured 3424.62 against a 50.0 threshold. The incorrect expectation was fixed, synthetic blur coverage was retained, and a later privacy audit replaced all undocumented identity/medical images with generated, visibly watermarked fixtures.
- A proposed multi-scale "text legibility" score rejected both pristine fixtures, rewarded severe downscaling, and accepted random noise. It was replaced with advisory pixel signals plus PII-free extraction completeness/confidence evidence.
- Retrieval evaluation initially returned correct but irrelevant extra citations. Adding citation precision exposed this, and retrieval queries were narrowed to stable deterministic flag codes.
- Workflow failure injection proves retries stop at two in the evaluated configuration and the case fails closed to human review.
- Stage-audit tests exposed a misleading trace for unreadable documents; the workflow now records quality and extraction failure without claiming deterministic validation ran.
- Conflicting allow/restrict policy effects now fail closed instead of producing an ambiguous automated explanation.
- Asset provenance review found realistic identity and patient data in legacy samples. Those files and the duplicated live benchmark were removed, generated synthetic replacements were added, and repeated-digit placeholder IDs now fail deterministic validation.

## Measured Evidence

- 89 offline unit tests pass; the Poppler integration check skips when the renderer is not installed.
- Two synthetic extraction fixtures pass schema validation and six critical-field exact-match checks; this verifies the offline contract, not model accuracy.
- Routing matrix: 6/6 correct, zero false approvals or false rejections.
- Document-quality matrix: 6/6 correct continue, human-review, or resubmission dispositions.
- Retrieval matrix: 7/7 expected policies within top three.
- Workflow matrix: 4/4 correct actions, citations, grounded explanations, and escalation behavior.
- Adversarial flag details do not propagate into queries, explanations, or audit output.
- Offline report records p50/p95 latency, retries, fallbacks, and zero model calls/cost.

These figures describe a small synthetic regression suite. Do not present them as production accuracy, scale, cost savings, or live-model performance.

## Likely Technical Questions

- How would durable human-review cases be stored idempotently?
- Which real-data failure taxonomy would determine whether to add embeddings or reranking?
- How would policy versions and citations be frozen per decision for auditability?
- How would authentication, requirement-based tool authorization, rate limiting, and data retention work?
- How would model/provider traces integrate with external telemetry without leaking PII?
- Which false-approval and false-rejection costs should set thresholds with product, risk, compliance, and operations?

## Next Steps

Use consented representative data; obtain policy-owner sign-off; add durable case and policy-version storage; integrate external metrics/traces; run load and chaos tests; define SLOs; add reviewer feedback; compare lexical, embedding, and reranked retrieval with the same evaluation set; and measure business impact only after deployment.
