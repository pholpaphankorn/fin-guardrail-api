# Project Requirement

This document captures the product and engineering requirements for this repository as a standalone side project. It focuses on the system behavior and expected outcomes.

## Core Outcome

Build an AI-native KYC and claims-review workflow that is useful, safe, and measurable. The system should automate routine document handling, surface evidence for uncertain cases, and keep high-stakes decisions under deterministic or human control.

## Required Capabilities

- Document upload with type, size, and integrity checks.
- Structured extraction from images and PDFs.
- Deterministic validation for identity, claim arithmetic, and policy rules.
- Retrieval of relevant synthetic policy or compliance rules with citations.
- Bounded workflow orchestration with typed tools and audit trails.
- Human review escalation for low-confidence or high-risk cases.
- Offline evaluations for accuracy, grounding, latency, retries, and fallback behavior.

## Safety Constraints

- Do not use an LLM as the final authority for irreversible decisions.
- Reject corrupt, oversized, or unsupported files before model execution.
- Redact sensitive data from logs, examples, and evaluation artifacts.
- Prefer deterministic Python for validations that can be encoded directly.
- Keep the workflow bounded; avoid open-ended autonomous agent behavior.

## Evidence Expectations

- Tests should cover workflow routing, tool allowlisting, extraction failures, and adversarial inputs.
- Evaluations should distinguish mock, offline, and live-model results.
- Documentation should explain what the system can and cannot automate.
- The UI should show extracted fields, validation findings, citations, and routing decisions.

## Scope Note

This document defines the current project scope and the behaviors the repository should implement and verify.
