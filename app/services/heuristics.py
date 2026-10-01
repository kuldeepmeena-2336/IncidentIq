from __future__ import annotations

from typing import Any


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def infer_severity(issue: dict[str, Any]) -> str:
    text = extract_text(issue.get("summary")) + " " + extract_text(issue.get("description"))
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["down", "outage", "failure", "critical", "panic", "security"]):
        return "CRITICAL"
    if any(keyword in lowered for keyword in ["latency", "timeout", "slow", "degraded", "warning"]):
        return "HIGH"
    if any(keyword in lowered for keyword in ["error", "exception", "db", "kafka", "auth", "login"]):
        return "MEDIUM"
    return "LOW"


def infer_service(issue: dict[str, Any]) -> str | None:
    text = extract_text(issue.get("summary")) + " " + extract_text(issue.get("description")) + " " + extract_text(issue.get("root_cause")) + " " + extract_text(issue.get("resolution")) + " " + " ".join(extract_text(value) for value in (issue.get("comments") or []) if isinstance(value, str))
    lowered = text.lower()

    if "cersai" in lowered or "credit bureau" in lowered or "bureau api" in lowered:
        return "cersai"
    if "loan" in lowered or "origination" in lowered:
        return "loan-origination"
    if "payment" in lowered:
        return "payments"
    if "auth" in lowered or "login" in lowered or "kyc" in lowered:
        return "identity"
    if "db" in lowered or "database" in lowered:
        return "database"
    if "kafka" in lowered:
        return "messaging"
    if "redis" in lowered:
        return "cache"
    if "fraud" in lowered or "risk" in lowered:
        return "fraud"
    return None


def infer_failure_type(issue: dict[str, Any]) -> str:
    text = extract_text(issue.get("summary")) + " " + extract_text(issue.get("description"))
    lowered = text.lower()
    if "timeout" in lowered:
        return "timeout"
    if "lag" in lowered:
        return "latency"
    if "connection" in lowered or "db" in lowered:
        return "database_connection"
    if "exception" in lowered:
        return "application_error"
    if "security" in lowered or "auth" in lowered:
        return "authentication"
    return "unknown"


def infer_missing_fields(issue: dict[str, Any], extracted: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    required = ["severity", "failure_type", "service"]
    for field in required:
        value = extracted.get(field)
        if value in (None, "", "UNKNOWN"):
            missing.append(field)
    if issue.get("summary") in (None, ""):
        missing.append("summary")
    return missing


def build_heuristic_extraction(payload: dict[str, Any]) -> dict[str, Any]:
    issue = payload.get("issue", {}) or payload
    severity = infer_severity(issue)
    service = infer_service(issue)
    failure_type = infer_failure_type(issue)
    extracted = {
        "severity": severity,
        "failure_type": failure_type,
        "service": service,
        "dependency": issue.get("dependency") or issue.get("component") or None,
        "root_cause": issue.get("root_cause") or "heuristic_inference",
        "resolution": issue.get("resolution") or "manual_review_required",
    }
    return extracted


def rank_results(query: str, incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lowered = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    for incident in incidents:
        text = " ".join(
            [
                str(incident.get("summary", "")),
                str(incident.get("service", "")),
                str(incident.get("failure_type", "")),
                str(incident.get("severity", "")),
                str(incident.get("root_cause", "")),
            ]
        ).lower()
        score = 1.0 if lowered in text else 0.0
        if lowered:
            score += sum(1 for token in lowered.split() if token in text) / max(len(lowered.split()), 1)
        scored.append((score, incident))
    return [incident for _, incident in sorted(scored, key=lambda item: item[0], reverse=True)]
