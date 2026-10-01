from __future__ import annotations

from typing import Any


def handle_ambiguous_query(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    if results:
        return {
            "needs_follow_up": False,
            "question": None,
        }

    q = (query or "").lower()
    if any(term in q for term in ["critical", "high", "urgent", "p1"]):
        return {
            "needs_follow_up": True,
            "question": "I did not find a direct match for the requested severity. Do you want me to broaden to related high-priority incidents or search by service or team?",
        }

    return {
        "needs_follow_up": True,
        "question": "I could not find a direct match. Can you share the affected service, assignee, or error type so I can narrow the search?",
    }
