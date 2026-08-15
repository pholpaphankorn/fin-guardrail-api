import pytest

from app.observability import MetricsRegistry


@pytest.mark.unit
def test_metrics_report_counts_and_percentiles_without_labels():
    registry = MetricsRegistry(max_samples=3)
    registry.increment("workflow_tool_failure_total")
    registry.observe_request(10.0)
    registry.observe_request(20.0)
    registry.observe_model(100.0, "responses")

    snapshot = registry.snapshot()

    assert snapshot["counts"] == {
        "model_calls_total": 1,
        "model_responses_total": 1,
        "requests_total": 2,
        "workflow_tool_failure_total": 1,
    }
    assert snapshot["request_latency_ms"]["p50"] == 15.0
    assert snapshot["model_latency_ms"]["p95"] == 100.0
    assert "labels" not in snapshot
