import os
import json
import re
import asyncio
from typing import Any, Dict, Tuple
from app.services.extractor import extract_thai_id

# Directory Paths
BASE_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_EVAL_DIR, "input")
GROUND_TRUTH_DIR = os.path.join(BASE_EVAL_DIR, "ground_truth")

# Default confidence floor if not specified in ground truth JSON
DEFAULT_MIN_CONFIDENCE = 0.70


def normalize_text(text: Any) -> str:
    """Strips leading/trailing whitespace and collapses multiple internal spaces into one."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\s+", " ", text.strip()).upper()


def evaluate_field(
    extracted_field: Any,
    ground_truth_field: Dict[str, Any],
) -> Tuple[bool, str]:
    """Evaluates an extracted field object/Pydantic model against a Ground Truth dictionary.
    
    Checks:
    1. Nullability / Missing cases
    2. Confidence score vs min confidence floor
    3. Boolean equality (for visual_checks)
    4. Whitespace-normalized Exact Match (for text fields)
    """
    # Parse extracted field (handles both Pydantic model objects and raw dicts)
    if hasattr(extracted_field, "model_dump"):
        ext_dict = extracted_field.model_dump()
    elif isinstance(extracted_field, dict):
        ext_dict = extracted_field
    else:
        ext_dict = {"value": extracted_field, "confidence": 1.0}

    extracted_val = ext_dict.get("value")
    extracted_conf = ext_dict.get("confidence", 0.0)

    gt_val = ground_truth_field.get("value")
    gt_min_conf = ground_truth_field.get("confidence", DEFAULT_MIN_CONFIDENCE)

    # 1. Check Nullability
    if gt_val is None:
        if extracted_val is None:
            return True, "Passed (both null)"
        return False, f"Value mismatch: expected null/None, got '{extracted_val}'"

    if extracted_val is None:
        return False, f"Value mismatch: expected '{gt_val}', got null/None"

    # 2. Check Confidence Score Floor
    if extracted_conf < gt_min_conf:
        return (
            False,
            f"Confidence low: got {extracted_conf:.2f}, expected >= {gt_min_conf:.2f}",
        )

    # 3. Check Booleans (e.g., visual_checks)
    if isinstance(gt_val, bool):
        if extracted_val == gt_val:
            return True, "Passed (boolean match)"
        return False, f"Boolean mismatch: got {extracted_val}, expected {gt_val}"

    # 4. Check Text/Formatted Strings (Normalized Exact Match)
    norm_extracted = normalize_text(extracted_val)
    norm_gt = normalize_text(gt_val)

    if norm_extracted == norm_gt:
        return True, "Passed (exact match)"

    return False, f"Value mismatch: got '{norm_extracted}', expected '{norm_gt}'"


async def evaluate_single_document(img_name: str) -> Dict[str, Any]:
    """Runs vision extraction on a single image and compares against ground truth."""
    base_name = os.path.splitext(img_name)[0]
    gt_path = os.path.join(GROUND_TRUTH_DIR, f"{base_name}.json")
    img_path = os.path.join(INPUT_DIR, img_name)

    if not os.path.exists(gt_path):
        print(f"⚠️  Skipping [{img_name}]: Ground truth file missing at {gt_path}")
        return {"skipped": True}

    # Load Ground Truth JSON
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Load Raw Image Bytes
    with open(img_path, "rb") as f:
        file_bytes = f.read()

    # Call Live LLM Vision Extractor
    extracted_data = await extract_thai_id(file_bytes)

    if extracted_data is None:
        print(f"❌ [{img_name}] Vision LLM returned None (Extraction Failed)")
        return {"accuracy": 0.0, "total_fields": 1, "passed_fields": 0}

    field_results = {}
    passed_count = 0
    total_count = 0

    # --- A. Evaluate Nested 'visual_checks' ---
    gt_visual_checks = ground_truth.get("visual_checks", {})
    ext_visual_checks = getattr(extracted_data, "visual_checks", None)

    for check_key, gt_check_obj in gt_visual_checks.items():
        total_count += 1
        ext_check_obj = getattr(ext_visual_checks, check_key, None) if ext_visual_checks else None
        
        passed, reason = evaluate_field(ext_check_obj, gt_check_obj)
        field_results[f"visual_checks.{check_key}"] = (passed, reason)
        if passed:
            passed_count += 1

    # --- B. Evaluate Root-Level Text Fields ---
    for field_key, gt_field_obj in ground_truth.items():
        if field_key == "visual_checks":
            continue  # Already evaluated above

        total_count += 1
        ext_field_obj = getattr(extracted_data, field_key, None)
        
        passed, reason = evaluate_field(ext_field_obj, gt_field_obj)
        field_results[field_key] = (passed, reason)
        if passed:
            passed_count += 1

    doc_accuracy = (passed_count / total_count) if total_count > 0 else 0.0

    # Print Report for Document
    print(f"\n📄 Document: {img_name}")
    print(f"   Accuracy: {doc_accuracy * 100:.1f}% ({passed_count}/{total_count} fields passed)")
    for field, (passed, reason) in field_results.items():
        if not passed:
            print(f"   ↳ ❌ {field}: {reason}")

    return {
        "accuracy": doc_accuracy,
        "total_fields": total_count,
        "passed_fields": passed_count,
    }


async def run_all_evals():
    """Main runner that scans input directory and evaluates all images."""
    # Ensure live LLM execution (disable mock mode)
    os.environ["USE_MOCK_LLM"] = "false"

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory does not exist: {INPUT_DIR}")
    if not os.path.exists(GROUND_TRUTH_DIR):
        raise FileNotFoundError(f"Ground truth directory does not exist: {GROUND_TRUTH_DIR}")

    image_files = [
        f for f in os.listdir(INPUT_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_files:
        print(f"No image files found in {INPUT_DIR}")
        return

    print("=" * 60)
    print(f"🚀 Starting LLM Evaluation Suite across {len(image_files)} image(s)...")
    print("=" * 60)

    total_system_fields = 0
    passed_system_fields = 0
    document_accuracies = []

    for img_name in image_files:
        res = await evaluate_single_document(img_name)
        if res.get("skipped"):
            continue

        total_system_fields += res["total_fields"]
        passed_system_fields += res["passed_fields"]
        document_accuracies.append(res["accuracy"])

    # Overall Summary Report
    if total_system_fields > 0:
        overall_field_acc = (passed_system_fields / total_system_fields) * 100
        avg_doc_acc = (sum(document_accuracies) / len(document_accuracies)) * 100

        print("\n" + "=" * 60)
        print("🎯 EVALUATION SUMMARY REPORT")
        print("=" * 60)
        print(f"Total Documents Tested   : {len(document_accuracies)}")
        print(f"Total Fields Evaluated   : {total_system_fields}")
        print(f"Fields Passed            : {passed_system_fields}")
        print(f"Field-Level Accuracy     : {overall_field_acc:.2f}%")
        print(f"Average Document Accuracy: {avg_doc_acc:.2f}%")
        print("=" * 60)

        # Threshold assertion for automated build pipelines
        assert overall_field_acc >= 90.0, (
            f"Benchmark failed! Overall accuracy ({overall_field_acc:.2f}%) "
            f"fell below target threshold of 90.0%"
        )


if __name__ == "__main__":
    asyncio.run(run_all_evals())