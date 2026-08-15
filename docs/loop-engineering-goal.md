/goal Refine Fin-Guardrail API into a production-quality AI-native KYC and claims-review system that satisfies the repository requirement document and provides strong, measurable evidence for a standalone side project.

The finished project must demonstrate that I can personally build, test, ship, and improve a practical financial AI workflow—not merely create an LLM demo.

## Execution Directive

Execute this goal autonomously in repeated, evidence-driven engineering loops. Start with the baseline and requirement-alignment matrix, then implement, test, evaluate, document, and commit each cohesive improvement. Do not stop after planning or after one feature. Continue until every completion criterion is satisfied or only explicitly documented external credentials, product guidance, or environment restrictions remain.

Read and follow `AGENTS.md` before making changes. Preserve unrelated user work. Create local commits throughout the loop, but do not push, rewrite history, or expand the project’s external authority without explicit permission.

## Target Capabilities

The project should provide credible evidence of:

- AI agents, workflows, typed tools, and operations automation.
- LLM extraction and structured outputs.
- Retrieval-augmented generation with source citations.
- Deterministic guardrails for financial and KYC decisions.
- Good judgment about what should and should not be automated.
- Human review for uncertain or high-risk cases.
- Evaluation of accuracy, hallucination, retrieval, tool use, latency, cost, security, compliance, and user trust.
- Production-quality Python and an end-to-end user experience.
- Measured impact without exaggerated claims.

## Product Direction

Evolve the application into an **AI KYC and Claims Review Copilot**.

The target workflow is:

1. Upload a document.
2. Validate image quality.
3. Perform structured vision extraction.
4. Apply deterministic KYC or claim checks.
5. Retrieve relevant synthetic policy or compliance rules.
6. Let the bounded workflow agent select approved tools and recommend the next action.
7. Approve, reject, request a clearer document, or create a human-review case.
8. Return an auditable explanation with policy citations.

The LLM may extract information, retrieve knowledge, summarize evidence, and recommend workflow actions. It must not independently make irreversible financial, compliance, identity, or medical decisions.

## Initial Baseline

Before implementing features:

1. Read `AGENTS.md`, `README.md`, `docs/requirement.md`, source code, tests, configuration, and recent Git history. Treat `docs/requirement.md` as the authoritative local record of the project requirement.
2. Inspect and preserve existing user changes.
3. Run the test, evaluation, formatting, and mock application commands.
4. Create or update `docs/requirement-alignment.md`, mapping every applicable technical and product expectation in `docs/requirement.md` to current evidence, identified gaps, planned improvements, and verification evidence.
5. Treat the historically observed 11 failing and 28 passing unit tests as a hypothesis to verify, not a permanent fact.
6. Repair repository correctness before adding major capabilities.

## Loop Engineering Process

Work in small, evidence-driven loops. For every loop:

1. Select the highest-value unresolved requirement.
2. State the user or operational problem being addressed.
3. Define a measurable success criterion.
4. Implement one cohesive improvement.
5. Add focused tests or evaluation cases.
6. Run the smallest relevant verification commands.
7. Compare the result with the previous baseline.
8. Keep the change only if it improves correctness, reliability, usability, or portfolio evidence.
9. Update:
   - `docs/requirement-alignment.md`
   - `docs/loop-log.md`
   - Machine-readable evaluation results
10. Commit the verified loop according to the version-control policy below.
11. Select the next highest-value unresolved requirement and repeat.

Do not weaken tests or metrics to make a loop pass.

## Implementation Priorities

### Phase 1 — Trustworthy Foundation

- Fix schema drift across Pydantic models, tests, mock responses, and evaluation scripts.
- Resolve all legitimate test failures.
- Make setup and documented commands reproducible.
- Validate uploads by type, size, image integrity, and processing limits.
- Return stable errors for corrupt documents and provider failures.
- Preserve deterministic validators as the authority for high-stakes rules.

### Phase 2 — Workflow and Tool Calling

Create an explicit, testable workflow orchestrator with typed state and tools such as:

- `extract_document`
- `check_image_quality`
- `validate_thai_id`
- `validate_claim_arithmetic`
- `retrieve_policy_rules`
- `request_document_resubmission`
- `create_human_review_case`
- `generate_customer_explanation`

Tool inputs and outputs must use typed schemas.

Use a bounded workflow or state machine. Do not create an open-ended autonomous agent. Record every tool call, input classification, result, error, and routing decision in a PII-safe audit trail.

Add tests proving that the workflow:

- Chooses the correct tool.
- Cannot invoke unauthorized tools.
- Handles tool failures.
- Stops after bounded retries.
- Escalates uncertainty.
- Never bypasses deterministic validation.

### Phase 3 — Useful, Grounded RAG

Create a small synthetic policy corpus covering KYC, document quality, claim eligibility, exclusions, and escalation rules.

Implement retrieval behind a replaceable interface. Begin with the simplest defensible retrieval method and add embeddings only when evaluation shows value.

Require generated explanations to cite retrieved policy sections. If supporting evidence is absent, the system must say it lacks sufficient policy evidence and escalate rather than invent a rule.

Evaluate:

- Retrieval recall@k.
- Citation correctness.
- Grounded-answer rate.
- Unsupported-claim rate.
- Performance with irrelevant or conflicting documents.
- Behavior under prompt injection inside uploaded documents.

### Phase 4 — Evaluation and Production Reliability

Build offline, deterministic evaluation suites for:

- Field extraction.
- KYC and risk routing.
- Claim arithmetic.
- Agent tool selection.
- Workflow task completion.
- Retrieval quality.
- Citation correctness.
- Hallucination and unsupported claims.
- Adversarial and malformed inputs.
- Human-escalation accuracy.

Report accuracy, false approvals, false rejections, p50/p95 latency, model calls, retries, fallback usage, and estimated or actual cost when available.

Separate mock, offline, and live-model results. Never present mock results as model performance.

Add timeouts, bounded retries, configuration validation, structured logging, request IDs, readiness checks, CI, containerization, and an operational runbook.

### Phase 5 — Product and Portfolio Evidence

Improve the UI into a review workspace showing:

- Extracted fields and confidence.
- Deterministic validation findings.
- Retrieved policy citations.
- Agent actions and tool history.
- Final routing decision.
- Why human review was required.
- Clear retry and error states.

Update the README with:

- The real financial workflow and users.
- Architecture and trust boundaries.
- What AI automates and what remains deterministic or human-controlled.
- Measured evaluation results.
- Security and privacy decisions.
- Latency and cost tradeoffs.
- Limitations.
- Reproducible demo steps.
- A Mermaid architecture diagram.

Create `docs/project-brief.md` explaining:

- The problem and why it matters.
- My personal engineering decisions.
- Difficult failures encountered.
- How evaluations changed the implementation.
- Production tradeoffs.
- Evidence of impact.
- What I would build next with real product and operations data.

## Engineering Constraints

- Never commit credentials, real IDs, or real medical information.
- Use only synthetic or properly sanitized fixtures.
- Redact PII from logs and evaluation artifacts.
- Do not add agent frameworks, vector databases, or infrastructure solely for résumé keywords.
- Do not use an LLM where deterministic Python is safer.
- Do not claim production scale, cost savings, or accuracy without evidence.
- If live credentials are unavailable, complete all offline work and clearly record the unverified live checks.

## Version-Control and Commit Policy

Commit completed work throughout the engineering loop.

For every successful loop:

1. Inspect `git status` and preserve unrelated user changes.
2. Keep the change cohesive and atomic. One commit should represent one clear improvement.
3. Include tests with the implementation when they directly verify its behavior.
4. Run all checks relevant to the loop and confirm that the change introduces no new failures.
5. Allow pre-existing baseline failures to remain temporarily only when documented in `docs/loop-log.md` with the next planned remediation.
6. Review the staged diff and run `git diff --check`.
7. Stage only intended paths explicitly. Do not use broad staging when unrelated changes exist.
8. Never commit credentials, `.env`, real personal documents, sensitive generated output, caches, or temporary files.
9. Never bypass Git hooks with `--no-verify`.
10. Do not amend, squash, rebase, force-push, or rewrite existing history unless explicitly requested.
11. Do not push commits to a remote unless explicitly requested.
12. Before committing, record the loop’s problem, change, verification commands, results, and planned commit message in `docs/loop-log.md`.
13. After committing, report the resulting commit hash in the progress update and final report. Do not modify the committed loop log merely to insert its own commit hash.

Use the repository’s established lowercase commit prefixes:

- `change:` for product behavior, architecture, fixes, and features.
- `test:` for isolated test or evaluation improvements.
- `chore:` for CI, dependencies, tooling, and configuration.
- `style:` for formatting-only changes.

Write concise, imperative commit messages that explain the outcome. Examples:

- `change: align extraction fixtures with confidence schema`
- `change: add bounded claim review workflow`
- `test: add policy retrieval grounding evaluation`
- `chore: run offline evaluations in CI`
- `change: redact sensitive fields from audit logs`

Do not create a commit when:

- Checks relevant to the loop fail.
- The change introduces a new regression.
- Formatting checks for changed files fail.
- The implementation is incomplete.
- The staged diff contains unrelated work.
- Results are fabricated or unverified.

If a loop contains several independently useful changes, split it into a small sequence of atomic commits. Do not create one commit per file or trivial edit.

At completion, report every created commit with its hash, message, purpose, and verification commands.

## Completion Criteria

Continue looping until:

- All unit tests pass with zero failures.
- Offline evaluations pass reproducibly.
- Formatting and CI checks pass.
- Both document workflows work in mock mode.
- The workflow agent uses typed, bounded, auditable tools.
- Unauthorized tool calls and unbounded retries are prevented.
- High-stakes outcomes cannot bypass deterministic rules or required human review.
- RAG responses contain verifiable policy citations.
- Unsupported policy answers safely escalate.
- Evaluation reports cover routing, retrieval, tool use, hallucination, latency, retries, fallbacks, and cost where measurable.
- Adversarial, prompt-injection, corrupt-file, and provider-failure tests exist.
- CI, container setup, health/readiness behavior, and an operational runbook exist.
- The UI demonstrates the complete review workflow.
- `docs/requirement-alignment.md` accounts for every applicable requirement in `docs/requirement.md`; technical requirements link to concrete code, tests, evaluations, or documentation, while any environment or communication constraints are recorded separately as contextual notes.
- `docs/project-brief.md` provides defensible technical discussion points.
- Every completed loop is represented by an atomic, verified commit.
- Commit history clearly communicates the engineering progression.
- No generated, sensitive, temporary, or unrelated files are committed.
- No commits are pushed without explicit permission.
- The final worktree is clean except for explicitly identified user-owned changes.
- Limitations and credential-dependent checks are honestly documented.

## Starting Instruction

Begin immediately by producing the baseline and requirement-alignment matrix. Then fix the broken correctness baseline before implementing agent or retrieval layers. After each verified commit, continue automatically with the next highest-value unmet completion criterion.

The most important design decision is the bounded workflow: the “agent” coordinates tools and evidence, while deterministic code or a human retains authority over risky financial decisions. This directly demonstrates the judgment the requirement calls for.
