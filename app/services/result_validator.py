from __future__ import annotations

from typing import Any


def validate_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for result in results or []:
        summary = str(result.get("summary") or "").strip()
        root_cause = str(result.get("root_cause") or "").strip()
        resolution = str(result.get("resolution") or "").strip()
        if not summary and not root_cause and not resolution:
            continue
        validated.append(result)
    return validated


def should_project_only_rca(query: str) -> bool:
    q = (query or "").lower()
    return any(phrase in q for phrase in [
        "only rca",
        "just rca",
        "only root cause",
        "just root cause",
        "only cause",
        "just cause",
    ])


def should_generate_communication(query: str, mode: str | None = None) -> str | None:
    q = (query or "").lower()
    if mode:
        return mode
    if any(phrase in q for phrase in ["draft a mail", "draft mail", "email", "mail to", "send mail", "manager email", "write mail"]):
        return "mail"
    if any(phrase in q for phrase in ["sms", "text message", "short message", "send sms", "draft sms"]):
        return "sms"
    return None
