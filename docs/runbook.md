# Operations Runbook

## Start and verify

Use mock mode for a deterministic local service:

```bash
cp .env.example .env
docker compose up --build
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

`/health/live` proves the process can serve requests. `/health/ready` additionally verifies that the policy corpus exists and that either mock mode or a live provider key is configured.

## Live provider

Set `USE_MOCK_LLM=false` and provide `OLLAMA_API_KEY` through the deployment secret store. `OLLAMA_HOST` and `VISION_MODEL` select the provider endpoint and model; clients read validated settings for each request rather than capturing credentials at import time. Never bake secrets into an image or commit `.env`. `VISION_TIMEOUT_SECONDS` accepts 1–120 seconds. A missing key returns readiness HTTP 503; a provider timeout returns HTTP 504.

`GET /api/v1/config` exposes the active extraction prompt versions without exposing credentials. Increment the relevant prompt version whenever instructions or output semantics change, then run the live extraction benchmark before promotion.

## Safe diagnostics

Every response includes `X-Request-ID`. Request logs contain only the ID, HTTP method, path, status, and latency—never query strings, bodies, extracted fields, names, identity numbers, or medical data. Use the ID to correlate application and gateway logs.

Run offline checks with:

```bash
python -m pytest tests/unit
python scripts/run_eval.py
black --check app tests scripts
```

The evaluation JSON is generated under `tests/evals/output/` and is intentionally ignored. It represents deterministic offline behavior, not live-model accuracy or production scale.

Credential-dependent tests require explicit authorization:

```bash
RUN_LIVE_E2E=true python -m pytest -m e2e
```

## Failure handling

- **400 PDF rejected:** send exactly one unencrypted, readable PDF page. Multi-page and password-protected PDFs are intentionally unsupported.
- **408 PDF processing timeout:** treat the document as untrusted or unusually complex; do not retry it indefinitely.
- **413 upload rejected:** keep documents below 10 MB and within the decoded-image/rendered-page safety limits.
- **415 media rejected:** send JPEG, PNG, or PDF content with the matching filename and media type.
- **503 PDF processing unavailable:** install Poppler (`pdfinfo` and `pdftoppm`) or use the supplied Docker image.
- **503 not ready:** confirm the policy corpus is present and configure mock mode or the provider key.
- **504 provider timeout:** check provider health and latency; do not raise the timeout above 120 seconds.
- **Human review fallback:** inspect stable flag codes and policy citations. Audit events intentionally omit document PII.

Do not copy production documents into tickets or evaluation fixtures. Reproduce failures with synthetic data and record only stable error or flag codes.

## Sensitive-history response

The pre-refinement Git history contains undocumented realistic identity and medical samples. The current working tree replaces them, but deleting files in a new commit will not erase earlier blobs. Before publishing or forking the repository, commit the removals, restrict access as appropriate, and have the repository owner decide whether a coordinated history purge is required. Do not rewrite shared history, force-push, or distribute replacement clone instructions without explicit authorization and stakeholder notification.
