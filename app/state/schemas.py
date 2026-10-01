from __future__ import annotations

from typing import Any, TypedDict


class IngestionState(TypedDict, total=False):
    jira_payload: dict[str, Any]
    normalized_issue: dict[str, Any]
    duplicate_check: bool
    extracted_fields: dict[str, Any]
    confidence: float
    missing_fields: list[str]
    final_status: str
    provider_used: str | None
    fallback_mode: bool


class RetrievalState(TypedDict, total=False):
    query: str
    structured_filters: dict[str, Any]
    semantic_query: str
    results: list[dict[str, Any]]
    summary: str
    confidence: float
    provider_used: str | None
    fallback_mode: bool
