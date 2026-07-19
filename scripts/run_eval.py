import sys
import os
import time
import asyncio
from unittest.mock import patch
from pydantic import BaseModel

# Ensure root directory path mapping constraints are resolved properly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from app.services.validator import evaluate_thai_id_risk, evaluate_medical_claim_risk

# --- EVALUATION DATA MATRIX SETTINGS ---
EVAL_DATASET = [
    {
        "case_name": "Valid Thai National ID Card Profile",
        "doc_type": "thai_id",
        "mock_extraction": ThaiIDExtraction(
            id_number="0000000000000",
            first_name_en="Jane",
            last_name_en="Doe",
            date_of_birth="1992-08-14",
            expiry_date="2034-05-11",  # Future date relative to 2026
        ),
        "expected_status": "APPROVED",
    },
    {
        "case_name": "Expired Thai National ID Card Profile",
        "doc_type": "thai_id",
        "mock_extraction": ThaiIDExtraction(
            id_number="0000000000000",
            first_name_en="John",
            last_name_en="Smith",
            date_of_birth="1985-01-20",
            expiry_date="2023-01-01",  # Already expired
        ),
        "expected_status": "REJECTED",
    },
    {
        "case_name": "Medical Claim Invoice - Balanced Ledger",
        "doc_type": "medical_receipt",
        "mock_extraction": MedicalReceiptExtraction(
            hospital_name="Bumrungrad International Hospital",
            receipt_date="2026-06-01",
            items=[
                {"description": "Blood Test Panel", "cost": 1500.0},
                {"description": "Antibiotics", "cost": 450.0},
            ],
            total_amount=1950.0,  # Correctly balanced math sum
        ),
        "expected_status": "APPROVED",
    },
    {
        "case_name": "Fraudulent Medical Claim - Arithmetic Tampering",
        "doc_type": "medical_receipt",
        "mock_extraction": MedicalReceiptExtraction(
            hospital_name="Samitivej Sukhumvit Hospital",
            receipt_date="2026-07-01",
            items=[
                {"description": "Outpatient Consultation", "cost": 1000.0},
                {"description": "Prescription Medicines", "cost": 300.0},
            ],
            total_amount=5000.0,  # Intentional total padding mismatch flag
        ),
        "expected_status": "FLAGGED_FOR_REVIEW",
    },
    {
        "case_name": "Medical Claim Policy Alert - Non-Covered Cosmetic Item",
        "doc_type": "medical_receipt",
        "mock_extraction": MedicalReceiptExtraction(
            hospital_name="Yanhee Clinic",
            receipt_date="2026-07-10",
            items=[
                {"description": "General Checkup Consultation", "cost": 500.0},
                {
                    "description": "Laser Skin Whitening Treatment",
                    "cost": 3500.0,
                },  # Policy violation keyword
            ],
            total_amount=4000.0,
        ),
        "expected_status": "FLAGGED_FOR_REVIEW",
    },
]


def run_pipeline_logic(doc_type: str, mock_data: BaseModel) -> str:
    """Simulates the internal app/main.py routing framework logic locally."""
    if doc_type == "thai_id":
        _, risk_score = evaluate_thai_id_risk(mock_data)
    else:
        _, risk_score = evaluate_medical_claim_risk(mock_data)

    if risk_score >= 0.7:
        return "REJECTED"
    elif risk_score > 0.0:
        return "FLAGGED_FOR_REVIEW"
    return "APPROVED"


def main():
    print("=" * 70)
    print("⚡ STARTING SYSTEM ENGINE PERFORMANCE & LOGIC EVALUATION SUITE ⚡")
    print("=" * 70)

    successful_matches = 0
    total_cases = len(EVAL_DATASET)
    start_time = time.time()

    for idx, case in enumerate(EVAL_DATASET, 1):
        print(f"\n[Test Case {idx}/{total_cases}] Evaluating: {case['case_name']}")

        # Track execution time metrics per evaluation pass
        case_start = time.time()
        actual_status = run_pipeline_logic(case["doc_type"], case["mock_extraction"])
        latency = (time.time() - case_start) * 1000

        # Assess correctness tracking checks
        is_correct = actual_status == case["expected_status"]
        if is_correct:
            successful_matches += 1
            status_symbol = "✅ PASSED"
        else:
            status_symbol = "❌ FAILED"

        print(f"  -> Type: {case['doc_type'].upper()}")
        print(f"  -> Latency: {latency:.2f} ms")
        print(
            f"  -> Pipeline Action Result: {actual_status} | Target: {case['expected_status']}"
        )
        print(f"  -> Check Summary Matrix Status: {status_symbol}")

    total_elapsed_time = time.time() - start_time
    global_accuracy = (successful_matches / total_cases) * 100

    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE PERFORMANCE VERDICT MATRICES SUMMARY")
    print("=" * 70)
    print(f"• Total Data Samples Processed: {total_cases}")
    print(f"• Successful Logic Matches:      {successful_matches}")
    print(f"• Global Operational Accuracy:  {global_accuracy:.1f}%")
    print(f"• Total Execution Performance:  {total_elapsed_time * 1000:.2f} ms")
    print("=" * 70)

    if global_accuracy == 100.0:
        print(
            "🚀 CRITICAL RESULT: Core System Gatekeeper Guardrails performing at target metrics!"
        )
        sys.exit(0)
    else:
        print(
            "⚠️ WARNING RESULT: System evaluation accuracy dropped beneath acceptable baselines."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
