from __future__ import annotations

import re
from typing import Any

SEVERITY_ALIASES = {
    "critical": {"critical", "urgent", "sev1", "sev-1", "p1", "high"},
    "high": {"high", "critical", "urgent", "sev1", "sev-1", "p1"},
    "medium": {"medium", "moderate"},
    "low": {"low", "minor"},
}

SERVICE_ALIASES = {
    "database": ["database", "db"],
    "auth": ["auth", "login"],
    "payments": ["payment", "payments"],
    "cache": ["cache", "redis"],
    "kafka": ["kafka"],
    "cersai": ["cersai", "bureau"],
    "kyc": ["kyc"],
    "loan": ["loan", "origination"],
    "fraud": ["fraud", "risk"],
    "security": ["security", "tls", "ssl"],
}


def normalize_severity(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for key, aliases in SEVERITY_ALIASES.items():
        if normalized in aliases or normalized == key:
            return key
    return normalized


def detect_intent(query: str) -> dict[str, Any]:
    q = (query or "").lower()
    intent: dict[str, Any] = {
        "asks_for_rca": any(phrase in q for phrase in ["rca", "root cause", "root-cause", "cause analysis"]),
        "asks_for_fix": any(phrase in q for phrase in ["fix", "resolution", "resolved", "fixed", "implemented"]),
        "asks_for_mail": any(phrase in q for phrase in ["draft a mail", "draft mail", "email", "mail to", "send mail", "manager email", "write mail"]),
        "asks_for_sms": any(phrase in q for phrase in ["sms", "text message", "short message", "send sms", "draft sms"]),
        "asks_for_summary": any(phrase in q for phrase in ["summary", "overview", "brief", "executive summary"]),
        "severity": None,
        "assignee": None,
        "service": None,
    }

    for sev, aliases in SEVERITY_ALIASES.items():
        if any(alias in q for alias in aliases):
            intent["severity"] = sev
            break

    by_match = re.search(r"\bby\s+([a-zA-Z][a-zA-Z0-9_.-]+)", q)
    if by_match:
        intent["assignee"] = by_match.group(1).strip()

    for service_name, aliases in SERVICE_ALIASES.items():
        if any(alias in q for alias in aliases):
            intent["service"] = service_name
            break

    return intent


def build_filters(query: str, existing_filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = dict(existing_filters or {})
    intent = detect_intent(query)
    if intent.get("severity"):
        filters["severity"] = intent["severity"]
    if intent.get("service"):
        filters["service"] = intent["service"]
    if intent.get("assignee"):
        filters["assignee"] = intent["assignee"]
    return filters
