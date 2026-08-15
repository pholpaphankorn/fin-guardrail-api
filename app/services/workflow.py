"""Bounded, deterministic orchestration for document-review actions."""

from enum import Enum
from typing import Callable

from pydantic import BaseModel, ConfigDict

from app.schemas import (
    PolicyCitation,
    WorkflowAction,
    WorkflowAuditEvent,
    WorkflowSummary,
)
from app.services.retrieval import LexicalPolicyRetriever, PolicyRetriever
from app.observability import metrics


class WorkflowTool(str, Enum):
    CHECK_IMAGE_QUALITY = "check_image_quality"
    EXTRACT_DOCUMENT = "extract_document"
    VALIDATE_THAI_ID = "validate_thai_id"
    VALIDATE_CLAIM = "validate_claim_arithmetic"
    RETRIEVE_POLICY = "retrieve_policy_rules"
    REQUEST_RESUBMISSION = "request_document_resubmission"
    CREATE_HUMAN_REVIEW = "create_human_review_case"
    GENERATE_EXPLANATION = "generate_customer_explanation"


class UnauthorizedToolError(ValueError):
    """Raised when orchestration requests a tool outside the approved registry."""


class PolicyConflictError(ValueError):
    """Raised when retrieved policy evidence has contradictory effects."""


class WorkflowContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_type: str
    status: str
    risk_score: float
    flag_codes: tuple[str, ...]


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str
    citations: tuple[PolicyCitation, ...] = ()


ToolHandler = Callable[[WorkflowContext], ToolResult]


def _validation_result(context: WorkflowContext) -> ToolResult:
    return ToolResult(
        summary=(
            f"Deterministic validation produced {context.status} with "
            f"{len(context.flag_codes)} flag code(s)."
        )
    )


def _stage_result(_: WorkflowContext) -> ToolResult:
    return ToolResult(summary="Pipeline stage result was recorded.")


def _request_resubmission(_: WorkflowContext) -> ToolResult:
    return ToolResult(summary="Requested a clearer or readable replacement document.")


def _create_human_review(_: WorkflowContext) -> ToolResult:
    return ToolResult(summary="Created a review task without copying document PII.")


def _generate_explanation(context: WorkflowContext) -> ToolResult:
    return ToolResult(
        summary=f"Generated a customer-safe explanation for {context.status}."
    )


class ToolRegistry:
    """Allowlisted workflow tools with injectable handlers for testing."""

    def __init__(
        self,
        overrides: dict[WorkflowTool, ToolHandler] | None = None,
        retriever: PolicyRetriever | None = None,
    ):
        self.retriever = retriever or LexicalPolicyRetriever()
        self._handlers: dict[WorkflowTool, ToolHandler] = {
            WorkflowTool.CHECK_IMAGE_QUALITY: _stage_result,
            WorkflowTool.EXTRACT_DOCUMENT: _stage_result,
            WorkflowTool.VALIDATE_THAI_ID: _validation_result,
            WorkflowTool.VALIDATE_CLAIM: _validation_result,
            WorkflowTool.RETRIEVE_POLICY: self._retrieve_policy,
            WorkflowTool.REQUEST_RESUBMISSION: _request_resubmission,
            WorkflowTool.CREATE_HUMAN_REVIEW: _create_human_review,
            WorkflowTool.GENERATE_EXPLANATION: _generate_explanation,
        }
        self._handlers.update(overrides or {})

    def _retrieve_policy(self, context: WorkflowContext) -> ToolResult:
        query = " ".join(context.flag_codes) if context.flag_codes else context.status
        rules = self.retriever.retrieve(query, context.document_type, limit=3)
        if not rules:
            raise LookupError("No supporting policy evidence was retrieved.")
        effects = {rule.effect for rule in rules}
        if "ALLOW" in effects and effects.difference({"ALLOW"}):
            raise PolicyConflictError("Retrieved policy effects conflict.")
        return ToolResult(
            summary=f"Retrieved {len(rules)} supporting policy section(s).",
            citations=tuple(rule.citation() for rule in rules),
        )

    def execute(self, tool_name: str, context: WorkflowContext) -> ToolResult:
        try:
            tool = WorkflowTool(tool_name)
        except ValueError as exc:
            raise UnauthorizedToolError(
                f"Tool '{tool_name}' is not authorized."
            ) from exc
        return self._handlers[tool](context)


def _flag_code(flag: str) -> str:
    """Keep only a stable code in audit events, never extracted values or notes."""
    return flag.split(":", 1)[0].strip() or "UNCLASSIFIED_FLAG"


class ReviewWorkflow:
    """Route deterministic results through a small, auditable tool state machine."""

    def __init__(
        self, registry: ToolRegistry | None = None, max_tool_attempts: int = 2
    ):
        if max_tool_attempts < 1 or max_tool_attempts > 3:
            raise ValueError("max_tool_attempts must be between 1 and 3")
        self.registry = registry or ToolRegistry()
        self.max_tool_attempts = max_tool_attempts

    def run(
        self,
        document_type: str,
        status: str,
        validation_flags: list[str],
        risk_score: float,
    ) -> WorkflowSummary:
        if document_type not in {"thai_id", "medical_receipt"}:
            raise ValueError(f"Unsupported document type: {document_type}")
        if status not in {"APPROVED", "FLAGGED_FOR_REVIEW", "REJECTED"}:
            raise ValueError(f"Unsupported validation status: {status}")
        expected_status = self._status_for_risk(risk_score)
        if status != expected_status:
            raise ValueError(
                f"Status {status} conflicts with deterministic risk routing {expected_status}."
            )

        context = WorkflowContext(
            document_type=document_type,
            status=status,
            risk_score=risk_score,
            flag_codes=tuple(_flag_code(flag) for flag in validation_flags),
        )
        events: list[WorkflowAuditEvent] = []
        citations: list[PolicyCitation] = []

        image_quality_succeeded = "BLURRY_IMAGE_DETECTED" not in context.flag_codes
        quality_review_required = (
            "DOCUMENT_QUALITY_REVIEW_REQUIRED" in context.flag_codes
        )
        self._record_stage(
            WorkflowTool.CHECK_IMAGE_QUALITY,
            image_quality_succeeded,
            (
                "Image and extraction quality evidence require human confirmation."
                if quality_review_required
                else (
                    "Image quality signals were recorded as advisory evidence."
                    if image_quality_succeeded
                    else "Image failed the legacy focus-quality gate."
                )
            ),
            context,
            events,
        )
        if not image_quality_succeeded:
            return self._complete_action(
                context,
                WorkflowAction.REQUEST_RESUBMISSION,
                WorkflowTool.REQUEST_RESUBMISSION,
                events,
                citations,
            )

        extraction_succeeded = "UNREADABLE_DOCUMENT" not in context.flag_codes
        self._record_stage(
            WorkflowTool.EXTRACT_DOCUMENT,
            extraction_succeeded,
            (
                "Structured document extraction succeeded."
                if extraction_succeeded
                else "Structured document extraction failed after bounded retries."
            ),
            context,
            events,
        )
        if not extraction_succeeded:
            return self._complete_action(
                context,
                WorkflowAction.REQUEST_RESUBMISSION,
                WorkflowTool.REQUEST_RESUBMISSION,
                events,
                citations,
            )

        validation_tool = (
            WorkflowTool.VALIDATE_THAI_ID
            if document_type == "thai_id"
            else WorkflowTool.VALIDATE_CLAIM
        )
        validation_succeeded = self._execute_bounded(validation_tool, context, events)
        if not validation_succeeded:
            metrics.increment("workflow_fallback_total")
            return WorkflowSummary(
                action=WorkflowAction.HUMAN_REVIEW,
                human_review_required=True,
                explanation="Deterministic validation was unavailable; human review is required.",
                policy_citations=[],
                audit_trail=events,
            )

        action, next_tool = self._select_action(context)
        return self._complete_action(context, action, next_tool, events, citations)

    def _complete_action(
        self,
        context: WorkflowContext,
        action: WorkflowAction,
        next_tool: WorkflowTool,
        events: list[WorkflowAuditEvent],
        citations: list[PolicyCitation],
    ) -> WorkflowSummary:
        retrieval_succeeded = self._execute_bounded(
            WorkflowTool.RETRIEVE_POLICY, context, events, citations
        )
        if not retrieval_succeeded or not citations:
            metrics.increment("workflow_fallback_total")
            return WorkflowSummary(
                action=WorkflowAction.HUMAN_REVIEW,
                human_review_required=True,
                explanation=(
                    "Supporting policy evidence was unavailable or conflicting; the "
                    "system did not invent a rule and requires human review."
                ),
                policy_citations=[],
                audit_trail=events,
            )

        succeeded = self._execute_bounded(next_tool, context, events)
        if not succeeded:
            action = WorkflowAction.HUMAN_REVIEW
            metrics.increment("workflow_fallback_total")

        metrics.increment(f"workflow_action_{action.value.lower()}_total")

        return WorkflowSummary(
            action=action,
            human_review_required=action == WorkflowAction.HUMAN_REVIEW,
            explanation=self._grounded_explanation(action, citations),
            policy_citations=citations,
            audit_trail=events,
        )

    @staticmethod
    def _record_stage(
        tool: WorkflowTool,
        succeeded: bool,
        summary: str,
        context: WorkflowContext,
        events: list[WorkflowAuditEvent],
    ) -> None:
        events.append(
            WorkflowAuditEvent(
                sequence=len(events) + 1,
                tool=tool.value,
                outcome="SUCCEEDED" if succeeded else "FAILED",
                summary=summary,
                flag_codes=list(context.flag_codes),
            )
        )
        metrics.increment(
            "workflow_tool_success_total"
            if succeeded
            else "workflow_tool_failure_total"
        )

    def _execute_bounded(
        self,
        tool: WorkflowTool,
        context: WorkflowContext,
        events: list[WorkflowAuditEvent],
        citations: list[PolicyCitation] | None = None,
    ) -> bool:
        for attempt in range(1, self.max_tool_attempts + 1):
            if attempt > 1:
                metrics.increment("workflow_tool_retries_total")
            try:
                result = self.registry.execute(tool.value, context)
                events.append(
                    WorkflowAuditEvent(
                        sequence=len(events) + 1,
                        tool=tool.value,
                        outcome="SUCCEEDED",
                        summary=result.summary,
                        flag_codes=list(context.flag_codes),
                    )
                )
                if citations is not None:
                    citations.extend(result.citations)
                metrics.increment("workflow_tool_success_total")
                return True
            except Exception:
                metrics.increment("workflow_tool_failure_total")
                events.append(
                    WorkflowAuditEvent(
                        sequence=len(events) + 1,
                        tool=tool.value,
                        outcome="FAILED",
                        summary=f"Tool attempt {attempt} failed safely.",
                        flag_codes=list(context.flag_codes),
                    )
                )
        return False

    @staticmethod
    def _grounded_explanation(
        action: WorkflowAction, citations: list[PolicyCitation]
    ) -> str:
        references = ", ".join(citation.policy_id for citation in citations)
        messages = {
            WorkflowAction.APPROVE: "Deterministic checks passed and the document may proceed.",
            WorkflowAction.REJECT: "Deterministic checks found a blocking document issue.",
            WorkflowAction.REQUEST_RESUBMISSION: "A clearer replacement document is required.",
            WorkflowAction.HUMAN_REVIEW: "Policy or validation findings require human review.",
        }
        return f"{messages[action]} Supporting policy: {references}."

    @staticmethod
    def _status_for_risk(risk_score: float) -> str:
        if risk_score < 0.0 or risk_score > 1.0:
            raise ValueError("risk_score must be between 0.0 and 1.0")
        if risk_score >= 0.7:
            return "REJECTED"
        if risk_score > 0.0:
            return "FLAGGED_FOR_REVIEW"
        return "APPROVED"

    @staticmethod
    def _select_action(
        context: WorkflowContext,
    ) -> tuple[WorkflowAction, WorkflowTool]:
        unreadable_codes = {"BLURRY_IMAGE_DETECTED", "UNREADABLE_DOCUMENT"}
        if unreadable_codes.intersection(context.flag_codes):
            return (
                WorkflowAction.REQUEST_RESUBMISSION,
                WorkflowTool.REQUEST_RESUBMISSION,
            )
        if context.status == "FLAGGED_FOR_REVIEW":
            return WorkflowAction.HUMAN_REVIEW, WorkflowTool.CREATE_HUMAN_REVIEW
        if context.status == "REJECTED":
            return WorkflowAction.REJECT, WorkflowTool.GENERATE_EXPLANATION
        return WorkflowAction.APPROVE, WorkflowTool.GENERATE_EXPLANATION


def build_workflow_summary(response: dict) -> WorkflowSummary:
    """Attach workflow routing to an existing deterministic API response."""
    return ReviewWorkflow().run(
        document_type=response["document_type"],
        status=response["status"],
        validation_flags=response["validation_flags"],
        risk_score=response["risk_score"],
    )
