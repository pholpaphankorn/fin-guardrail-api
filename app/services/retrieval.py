"""Replaceable retrieval over a small, synthetic compliance policy corpus."""

import json
import re
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

from app.schemas import PolicyCitation

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "policies" / "policies.json"
)


class PolicyRule(BaseModel):
    policy_id: str
    title: str
    section: str
    document_types: list[str]
    keywords: list[str]
    guidance: str
    effect: Literal["ALLOW", "DENY", "REVIEW", "RESUBMIT"]

    def citation(self) -> PolicyCitation:
        return PolicyCitation(
            policy_id=self.policy_id,
            title=self.title,
            section=self.section,
        )


class PolicyRetriever(Protocol):
    def retrieve(
        self, query: str, document_type: str, limit: int = 3
    ) -> list[PolicyRule]: ...


def _tokens(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ").replace("-", " ")
    return set(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


class LexicalPolicyRetriever:
    """Deterministic lexical baseline suitable for offline evaluation."""

    def __init__(self, policy_path: Path = DEFAULT_POLICY_PATH):
        raw_rules = json.loads(policy_path.read_text(encoding="utf-8"))
        self.rules = [PolicyRule.model_validate(rule) for rule in raw_rules]

    def retrieve(
        self, query: str, document_type: str, limit: int = 3
    ) -> list[PolicyRule]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        query_tokens = _tokens(query)
        ranked: list[tuple[int, str, PolicyRule]] = []

        for rule in self.rules:
            if (
                document_type not in rule.document_types
                and "all" not in rule.document_types
            ):
                continue
            searchable = " ".join(
                [
                    rule.policy_id,
                    rule.title,
                    rule.section,
                    *rule.keywords,
                    rule.guidance,
                ]
            )
            overlap = len(query_tokens.intersection(_tokens(searchable)))
            if overlap:
                ranked.append((overlap, rule.policy_id, rule))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        if not ranked:
            return []
        top_score = ranked[0][0]
        return [rule for score, _, rule in ranked if score == top_score][:limit]
