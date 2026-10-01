from __future__ import annotations

from typing import Any


def format_response(query: str, results: list[dict[str, Any]], summary: str, communication_draft: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": query,
        "results": results,
        "summary": summary,
        "communication_draft": communication_draft,
    }

    if communication_draft:
        payload["final_response"] = communication_draft
    elif results:
        payload["final_response"] = summary
    else:
        payload["final_response"] = f"No matching incidents found for '{query}'."

    return payload
