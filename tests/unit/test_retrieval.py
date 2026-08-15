import pytest

from app.services.retrieval import LexicalPolicyRetriever


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "document_type", "expected_policy"),
    [
        ("ARITHMETIC_MISMATCH invoice total", "medical_receipt", "CLAIM-FIN-001"),
        ("ID_CHECKSUM_FAILED Thai ID", "thai_id", "KYC-ID-001"),
        ("BLURRY_IMAGE_DETECTED", "thai_id", "DOC-QUALITY-001"),
        ("LOW_FIELD_CONFIDENCE human review", "thai_id", "OPS-CONFIDENCE-001"),
    ],
)
def test_lexical_retrieval_returns_expected_policy(
    query, document_type, expected_policy
):
    results = LexicalPolicyRetriever().retrieve(query, document_type, limit=3)

    assert expected_policy in {rule.policy_id for rule in results}


@pytest.mark.unit
def test_retrieval_filters_wrong_document_type():
    results = LexicalPolicyRetriever().retrieve(
        "arithmetic mismatch invoice total", "thai_id", limit=5
    )

    assert "CLAIM-FIN-001" not in {rule.policy_id for rule in results}


@pytest.mark.unit
def test_retrieval_rejects_invalid_limit():
    with pytest.raises(ValueError):
        LexicalPolicyRetriever().retrieve("approved", "thai_id", limit=0)
