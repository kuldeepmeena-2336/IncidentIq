from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.services.database import SessionLocal, init_db, save_incident
from app.services.heuristics import build_heuristic_extraction, infer_missing_fields
from app.services.provider_router import provider_router
from app.services.vector_store import VectorStoreService
from app.state.schemas import IngestionState
from app.tools.jira_tool import JiraTool


def ingest_issue(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    jira_tool = JiraTool()
    vector_store = VectorStoreService()
    state: IngestionState = {
        "jira_payload": payload,
        "normalized_issue": payload.get("issue", {}) if isinstance(payload, dict) else {},
        "duplicate_check": False,
        "extracted_fields": {},
        "confidence": 0.0,
        "missing_fields": [],
        "final_status": "received",
        "provider_used": None,
        "fallback_mode": True,
    }

    graph = StateGraph(IngestionState)

    def normalize_node(state: IngestionState) -> IngestionState:
        payload = state.get("jira_payload", {})
        normalized = jira_tool.parse_payload(payload)
        state["normalized_issue"] = {
            "id": normalized.get("issue_key") or payload.get("issue", {}).get("id") or payload.get("id"),
            "summary": normalized.get("summary"),
            "description": normalized.get("description"),
            "status": normalized.get("status"),
            "priority": normalized.get("priority"),
            "issue_type": normalized.get("issue_type"),
            "project": normalized.get("project"),
            "components": normalized.get("components", []),
            "labels": normalized.get("labels", []),
            "assignee": normalized.get("assignee"),
            "reporter": normalized.get("reporter"),
            "label": normalized.get("label"),
            "comments": normalized.get("comments", []),
            "root_cause": normalized.get("root_cause"),
            "resolution": normalized.get("resolution"),
        }
        return state

    def duplicate_node(state: IngestionState) -> IngestionState:
        state["duplicate_check"] = False
        return state

    def extract_node(state: IngestionState) -> IngestionState:
        issue = state.get("normalized_issue", {})
        adapter = provider_router.get_llm_adapter()

        if adapter is not None:
            try:
                prompt = (
                    "Extract incident metadata in JSON with fields: severity, failure_type, service, dependency, root_cause, resolution, team. "
                    f"Issue summary: {issue.get('summary', '')}. Description: {issue.get('description', '')}. Comments: {issue.get('comments', [])}."
                )
                response = adapter.chat(prompt, system_prompt="You are an incident extraction assistant.")
                state["provider_used"] = adapter.provider.name
                state["fallback_mode"] = False
                state["confidence"] = 0.85
                state["extracted_fields"] = {
                    "severity": "MEDIUM",
                    "failure_type": "unknown",
                    "service": None,
                    "dependency": None,
                    "root_cause": issue.get("root_cause") or "provider_inferred",
                    "resolution": issue.get("resolution") or "manual_review_required",
                    "team": issue.get("label") or "unknown",
                }
                content = response.get("content", "")
                if isinstance(content, str) and "{" in content:
                    import json

                    try:
                        parsed = json.loads(content[content.find("{") : content.rfind("}") + 1])
                        if isinstance(parsed, dict):
                            for key, value in parsed.items():
                                if value not in (None, ""):
                                    state["extracted_fields"][key] = value
                    except Exception:
                        pass
                state["missing_fields"] = infer_missing_fields(issue, state["extracted_fields"])
                return state
            except Exception:
                pass

        extracted = build_heuristic_extraction({"issue": issue})
        if issue.get("root_cause"):
            extracted["root_cause"] = issue["root_cause"]
        if issue.get("resolution"):
            extracted["resolution"] = issue["resolution"]
        if issue.get("label"):
            extracted["team"] = issue["label"]
        missing = infer_missing_fields(issue, extracted)
        state["extracted_fields"] = extracted
        state["missing_fields"] = missing
        state["confidence"] = 0.55 if not missing else 0.35
        state["provider_used"] = "heuristic_fallback"
        state["fallback_mode"] = True
        return state

    def persist_node(state: IngestionState) -> IngestionState:
        issue = state.get("normalized_issue", {})
        incident_id = str(issue.get("id") or state.get("jira_payload", {}).get("issue", {}).get("id") or "incident-unknown")
        incident = {
            "id": incident_id,
            "external_id": incident_id,
            "source": "jira",
            "summary": issue.get("summary"),
            "description": issue.get("description"),
            "service": state.get("extracted_fields", {}).get("service"),
            "severity": state.get("extracted_fields", {}).get("severity") or "MEDIUM",
            "failure_type": state.get("extracted_fields", {}).get("failure_type"),
            "dependency": state.get("extracted_fields", {}).get("dependency"),
            "root_cause": state.get("extracted_fields", {}).get("root_cause") or issue.get("root_cause"),
            "resolution": state.get("extracted_fields", {}).get("resolution") or issue.get("resolution"),
            "team": state.get("extracted_fields", {}).get("team") or issue.get("label"),
            "assignee": issue.get("assignee"),
            "reporter": issue.get("reporter"),
            "raw_payload": state.get("jira_payload"),
            "confidence": state.get("confidence", 0.0),
            "missing_fields": state.get("missing_fields", []),
            "completeness": 1.0 - (len(state.get("missing_fields", [])) / 6.0) if state.get("missing_fields") else 1.0,
            "status": "partial" if state.get("missing_fields") else "stored",
            "is_partial": bool(state.get("missing_fields")),
        }
        db = SessionLocal()
        try:
            saved = save_incident(db, incident)
        finally:
            db.close()

        search_text = " ".join(
            [
                str(issue.get("summary") or ""),
                str(issue.get("description") or ""),
                str(issue.get("root_cause") or state.get("extracted_fields", {}).get("root_cause") or ""),
                str(issue.get("resolution") or state.get("extracted_fields", {}).get("resolution") or ""),
                str(issue.get("label") or state.get("extracted_fields", {}).get("team") or ""),
                str(issue.get("project") or ""),
                str(issue.get("assignee") or ""),
                str(issue.get("reporter") or ""),
            ]
        )
        vector_store.save_embedding(incident_id, search_text, vector_store.build_text_embedding(search_text))

        state["final_status"] = saved.get("status", "stored")
        return state

    def finalize_node(state: IngestionState) -> IngestionState:
        if state.get("missing_fields"):
            state["final_status"] = "partial_record_stored"
        else:
            state["final_status"] = "stored"
        return state

    graph.add_node("normalize", normalize_node)
    graph.add_node("duplicate", duplicate_node)
    graph.add_node("extract", extract_node)
    graph.add_node("persist", persist_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "duplicate")
    graph.add_edge("duplicate", "extract")
    graph.add_edge("extract", "persist")
    graph.add_edge("persist", "finalize")
    graph.add_edge("finalize", END)

    compiled = graph.compile()
    return compiled.invoke(state)
