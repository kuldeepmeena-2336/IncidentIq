from __future__ import annotations

from typing import Any

from app.services.intent_router import build_filters, detect_intent
from app.services.result_validator import should_generate_communication, should_project_only_rca, validate_results


class QueryOrchestrator:
    def plan_before_search(self, query: str, existing_filters: dict[str, Any] | None = None) -> dict[str, Any]:
        intent = detect_intent(query)
        filters = build_filters(query, existing_filters)
        return {
            "intent": intent,
            "filters": filters,
            "action": self._derive_action(query),
        }

    def plan_after_search(self, query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        validated = validate_results(results)
        communication_mode = should_generate_communication(query)
        project_only_rca = should_project_only_rca(query)
        return {
            "validated": validated,
            "communication_mode": communication_mode,
            "project_only_rca": project_only_rca,
            "action": self._derive_action(query, communication_mode=communication_mode, project_only_rca=project_only_rca),
        }

    @staticmethod
    def _derive_action(
        query: str,
        *,
        communication_mode: str | None = None,
        project_only_rca: bool | None = None,
    ) -> str:
        if communication_mode:
            return f"draft_{communication_mode}"
        if project_only_rca or should_project_only_rca(query):
            return "rca_only"
        if any(phrase in (query or "").lower() for phrase in ["summary", "overview", "brief", "executive summary"]):
            return "summary"
        return "search"
