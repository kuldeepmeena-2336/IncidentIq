from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.models.incident import IncidentORM
from app.services.communication_tools import build_communication_draft
from app.services.database import SessionLocal
from app.services.intent_router import build_filters, detect_intent
from app.services.query_orchestrator import QueryOrchestrator
from app.services.result_validator import should_generate_communication, should_project_only_rca, validate_results
from app.services.provider_router import provider_router
from app.services.search_service import IncidentSearchService
from app.services.vector_store import VectorStoreService
from app.services.follow_up_handler import handle_ambiguous_query
from app.services.response_formatter import format_response


class RetrievalState(TypedDict, total=False):
    query: str
    structured_filters: dict[str, Any]
    semantic_query: str
    results: list[dict[str, Any]]
    summary: str
    confidence: float
    provider_used: str | None
    fallback_mode: bool
    communication_draft: str | None
    follow_up_question: str | None


def _load_incident_rows() -> list[dict[str, Any]]:
    try:
        db = SessionLocal()
        rows = db.query(IncidentORM).all()
        db.close()
        return [
            {
                "id": row.id,
                "summary": row.summary or "",
                "service": row.service or "",
                "severity": row.severity or "",
                "failure_type": row.failure_type or "",
                "root_cause": row.root_cause or "",
                "resolution": row.resolution or "",
                "team": row.team or "",
                "assignee": row.assignee or "",
                "reporter": row.reporter or "",
                "status": row.status or "",
                "description": row.description or "",
                "raw_payload": row.raw_payload or {},
            }
            for row in rows
        ]
    except Exception:
        return []


def _is_only_rca_query(query: str) -> bool:
    q = query.lower()
    return any(
        phrase in q
        for phrase in [
            "only rca",
            "just rca",
            "only root cause",
            "just root cause",
            "only cause",
            "just cause",
        ]
    )


def _is_mail_request(query: str) -> bool:
    q = query.lower()
    return any(phrase in q for phrase in ["draft a mail", "draft mail", "email", "mail to", "send mail", "manager email", "write mail"])


def _is_sms_request(query: str) -> bool:
    q = query.lower()
    return any(phrase in q for phrase in ["sms", "text message", "short message", "send sms", "draft sms"])


def _validate_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for result in results:
        root_cause = str(result.get("root_cause") or "").strip()
        resolution = str(result.get("resolution") or "").strip()
        summary = str(result.get("summary") or "").strip()
        if not summary and not root_cause and not resolution:
            continue
        if not root_cause and not resolution and not summary:
            continue
        validated.append(result)
    return validated


def _project_results_for_query(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _is_only_rca_query(query):
        return results

    projected: list[dict[str, Any]] = []
    for result in results:
        root_cause = str(result.get("root_cause") or "").strip()
        if not root_cause:
            continue
        projected.append(
            {
                "id": result.get("id"),
                "summary": result.get("summary") or "",
                "root_cause": root_cause,
                "team": result.get("team") or "",
                "score": result.get("score", 0.0),
            }
        )
    return projected


def retrieve_incidents(query: str) -> dict[str, Any]:
    state: RetrievalState = {
        "query": query,
        "structured_filters": {},
        "semantic_query": query,
        "results": [],
        "summary": "No results yet",
        "confidence": 0.0,
        "provider_used": None,
        "fallback_mode": True,
        "communication_draft": None,
        "follow_up_question": None,
    }

    graph = StateGraph(RetrievalState)
    search_service = IncidentSearchService()
    vector_store = VectorStoreService()
    orchestrator = QueryOrchestrator()

    def parse_query_node(state: RetrievalState) -> RetrievalState:
        plan = orchestrator.plan_before_search(query, state.get("structured_filters"))
        state["structured_filters"] = plan["filters"]
        state["semantic_query"] = query.strip()
        return state

    def run_search_node(state: RetrievalState) -> RetrievalState:
        filters = state.get("structured_filters", {})
        heuristic_results = search_service.search(query, filters=filters, limit=10)
        plan_after = orchestrator.plan_after_search(query, heuristic_results)
        validated_results = plan_after["validated"]

        if not validated_results:
            state["results"] = []
            state["confidence"] = 0.0
            state["provider_used"] = "database_search"
            state["fallback_mode"] = True
            follow_up = handle_ambiguous_query(query, [])
            state["follow_up_question"] = follow_up.get("question")
            state["summary"] = follow_up.get("question") or f"No matching incidents found for '{query}'."
            return state

        if plan_after["project_only_rca"]:
            projected_results = []
            for result in validated_results:
                root_cause = str(result.get("root_cause") or "").strip()
                if root_cause:
                    projected_results.append(
                        {
                            "id": result.get("id"),
                            "summary": result.get("summary") or "",
                            "root_cause": root_cause,
                            "team": result.get("team") or "",
                            "score": result.get("score", 0.0),
                        }
                    )
            state["results"] = projected_results
        else:
            state["results"] = validated_results

        state["confidence"] = max((item.get("score", 0.0) for item in validated_results), default=0.0)
        state["provider_used"] = "database_search"
        state["fallback_mode"] = True
        return state

    def summarize_node(state: RetrievalState) -> RetrievalState:
        results = state.get("results", [])
        if results:
            communication_mode = should_generate_communication(query)
            if communication_mode:
                draft = build_communication_draft(query, results, mode=communication_mode)
                state["communication_draft"] = draft
                issue_lines = []
                for result in results[:5]:
                    issue_lines.append(
                        f"- {result.get('summary') or 'Untitled issue'} | service={result.get('service') or 'unknown'} | severity={result.get('severity') or 'unknown'} | root_cause={result.get('root_cause') or 'not captured'} | resolution={result.get('resolution') or 'not captured'}"
                    )
                state["summary"] = "Search completed from stored incidents:\n" + "\n".join(issue_lines) + "\n\nDraft " + ("SMS" if communication_mode == "sms" else "mail") + ":\n" + draft
                return state

            if should_project_only_rca(query):
                issue_lines = []
                for result in results[:5]:
                    issue_lines.append(f"- {result.get('id') or 'unknown'}: {result.get('root_cause') or 'root cause not captured'}")
                state["summary"] = "Only RCA for matching incidents:\n" + "\n".join(issue_lines)
                return state

            issue_lines = []
            for result in results[:5]:
                issue_lines.append(
                    f"- {result.get('summary') or 'Untitled issue'} | service={result.get('service') or 'unknown'} | severity={result.get('severity') or 'unknown'} | root_cause={result.get('root_cause') or 'not captured'} | resolution={result.get('resolution') or 'not captured'}"
                )
            state["summary"] = "Search completed from stored incidents:\n" + "\n".join(issue_lines)
            return state

        follow_up = handle_ambiguous_query(query, [])
        state["summary"] = follow_up.get("question") or f"No matching incidents found for '{query}'."
        state["follow_up_question"] = follow_up.get("question")
        state["provider_used"] = "database_search"
        state["fallback_mode"] = True
        return state

    graph.add_node("parse_query", parse_query_node)
    graph.add_node("run_search", run_search_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("parse_query")
    graph.add_edge("parse_query", "run_search")
    graph.add_edge("run_search", "summarize")
    graph.add_edge("summarize", END)

    compiled = graph.compile()
    final_state = compiled.invoke(state)
    response = format_response(
        final_state.get("query", query),
        final_state.get("results", []),
        final_state.get("summary", "No results yet"),
        final_state.get("communication_draft"),
    )
    response["structured_filters"] = final_state.get("structured_filters", {})
    response["semantic_query"] = final_state.get("semantic_query", query)
    response["confidence"] = final_state.get("confidence", 0.0)
    response["provider_used"] = final_state.get("provider_used", "database_search")
    response["fallback_mode"] = final_state.get("fallback_mode", True)
    response["follow_up_question"] = final_state.get("follow_up_question")
    return response