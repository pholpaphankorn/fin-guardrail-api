import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.services.validator import (
    evaluate_thai_id_risk,
    evaluate_medical_claim_risk,
    calculate_status_and_reasoning,
    build_unreadable_document_response,
)
from app.services.extractor import (
    PROMPT_VERSIONS,
    extract_thai_id,
    extract_medical_receipt,
)
from app.services.image_processor import (
    ImageQualityAssessment,
    MAX_UPLOAD_BYTES,
    evaluate_image_quality_dependency,
)
from app.services.quality import build_document_quality_report
from app.services.retrieval import DEFAULT_POLICY_PATH
from app.services.workflow import build_workflow_summary
from app.config import get_settings
from app.observability import metrics
from app.schemas import QualityDisposition, RiskAssessmentResponse

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
SAMPLE_DIR = PROJECT_DIR / "data" / "mock_docs"
request_logger = logging.getLogger("fin_guardrail.requests")

app = FastAPI(
    title="Fin-Guardrail API",
    description="Automated Onboarding & Claims Risk Engine with Hybrid LLM/Deterministic Guardrails",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/samples", StaticFiles(directory=SAMPLE_DIR), name="samples")


@app.middleware("http")
async def request_observability(request, call_next):
    """Emit a correlation ID and structured metadata without bodies or query strings."""
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        request_logger.exception(
            json.dumps(
                {
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                }
            )
        )
        raise
    latency_ms = (time.perf_counter() - started) * 1000
    metrics.observe_request(latency_ms)
    response.headers["X-Request-ID"] = request_id
    request_logger.info(
        json.dumps(
            {
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 3),
            }
        )
    )
    return response


def finalize_response(response: dict) -> dict:
    """Attach the bounded workflow decision to a deterministic response."""
    response["workflow"] = build_workflow_summary(response).model_dump(mode="json")
    return response


def attach_quality(response: dict, quality) -> dict:
    """Attach PII-free quality evidence before workflow routing."""
    response["quality"] = quality.model_dump(mode="json")
    return finalize_response(response)


@app.get("/")
async def root():
    """Serves the document validation user interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fin-guardrail-api"}


@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    settings = get_settings()
    checks = {
        "policy_corpus": DEFAULT_POLICY_PATH.is_file(),
        "vision_provider": settings.live_provider_ready,
    }
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/metrics")
async def runtime_metrics():
    """Expose aggregate PII-free counters and bounded latency percentiles."""
    return metrics.snapshot()


@app.get("/api/v1/config")
async def ui_config():
    """Returns non-sensitive runtime details needed by the demo UI."""
    return {
        "demo_mode": get_settings().use_mock_llm,
        "vision_provider": "Ollama Cloud",
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "prompt_versions": PROMPT_VERSIONS,
    }


@app.post("/api/v1/validate/thai-id", response_model=RiskAssessmentResponse)
async def validate_thai_id_endpoint(
    image_quality: ImageQualityAssessment = Depends(evaluate_image_quality_dependency),
):
    """Validates Thai ID Cards for onboarding & KYC compliance."""
    # Image heuristics are advisory. Structured extraction evidence determines whether
    # the document can continue, needs human confirmation, or needs resubmission.
    extracted_data = await extract_thai_id(image_quality.image_bytes)
    quality = build_document_quality_report("thai_id", image_quality, extracted_data)

    if extracted_data is None:
        return attach_quality(
            build_unreadable_document_response(
                "thai_id",
                "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries.",
            ),
            quality,
        )

    if quality.disposition == QualityDisposition.REQUEST_RESUBMISSION:
        return attach_quality(
            build_unreadable_document_response(
                "thai_id",
                "UNREADABLE_DOCUMENT: Structured extraction did not recover enough required information.",
            ),
            quality,
        )

    # Deterministic validators remain authoritative for identity decisions.
    flags, risk_score = evaluate_thai_id_risk(extracted_data)
    if quality.disposition == QualityDisposition.HUMAN_REVIEW:
        flags.append(
            "DOCUMENT_QUALITY_REVIEW_REQUIRED: Extraction evidence or advisory image signals require human confirmation."
        )
        risk_score = max(risk_score, 0.5)
    status, reasoning = calculate_status_and_reasoning(risk_score)

    return attach_quality(
        {
            "document_type": "thai_id",
            "status": status,
            "extracted_data": extracted_data.model_dump(),
            "validation_flags": flags,
            "risk_score": risk_score,
            "reasoning": reasoning,
        },
        quality,
    )


@app.post("/api/v1/validate/medical-receipt", response_model=RiskAssessmentResponse)
async def validate_medical_receipt_endpoint(
    image_quality: ImageQualityAssessment = Depends(evaluate_image_quality_dependency),
):
    """Validates Medical Receipts for insurance claims processing."""
    extracted_data = await extract_medical_receipt(image_quality.image_bytes)
    quality = build_document_quality_report(
        "medical_receipt", image_quality, extracted_data
    )

    if extracted_data is None:
        return attach_quality(
            build_unreadable_document_response(
                "medical_receipt",
                "UNREADABLE_DOCUMENT: Failed to parse required document fields after retries.",
            ),
            quality,
        )

    if quality.disposition == QualityDisposition.REQUEST_RESUBMISSION:
        return attach_quality(
            build_unreadable_document_response(
                "medical_receipt",
                "UNREADABLE_DOCUMENT: Structured extraction did not recover enough required information.",
            ),
            quality,
        )

    # Deterministic arithmetic and coverage checks remain authoritative.
    flags, risk_score = evaluate_medical_claim_risk(extracted_data)
    if quality.disposition == QualityDisposition.HUMAN_REVIEW:
        flags.append(
            "DOCUMENT_QUALITY_REVIEW_REQUIRED: Extraction evidence or advisory image signals require human confirmation."
        )
        risk_score = max(risk_score, 0.5)
    status, reasoning = calculate_status_and_reasoning(risk_score)

    return attach_quality(
        {
            "document_type": "medical_receipt",
            "status": status,
            "extracted_data": extracted_data.model_dump(),
            "validation_flags": flags,
            "risk_score": risk_score,
            "reasoning": reasoning,
        },
        quality,
    )
