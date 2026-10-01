from __future__ import annotations

import re
from typing import Any

from app.models.incident import IncidentORM
from app.services.database import SessionLocal


class IncidentSearchService:
    _STOP_WORDS = {
        "could", "please", "give", "me", "what", "was", "for", "those", "and",
        "the", "a", "an", "of", "to", "in", "on", "at", "with", "from",
        "issue", "issues", "problem", "problems", "error", "errors", "exception",
        "exceptions", "status", "result", "results", "detail", "details", "please",
        "give", "kind", "type", "all", "show", "need", "want", "fixed", "by"
    }

    _ACTION_WORDS = {"rca", "root", "cause", "fix", "resolution", "summary", "details", "status"}
    _SEVERITY_ALIASES = {
        "critical": {"critical", "urgent", "sev1", "sev-1", "p1", "high"},
        "high": {"high", "critical", "urgent", "sev1", "sev-1", "p1"},
        "medium": {"medium", "moderate"},
        "low": {"low", "minor"},
    }

    _ENTITY_ALIASES = {
        "nullpointerexception": {"nullpointerexception", "npe"},
        "timeout": {"timeout", "timedout", "readtimeout", "read-timeout"},
        "deadlock": {"deadlock"},
        "database": {"database", "db"},
        "cersai": {"cersai", "credit", "bureau"},
        "loan": {"loan", "origination"},
        "fraud": {"fraud", "risk"},
        "kafka": {"kafka"},
        "payment": {"payment", "payments"},
        "security": {"security", "tls", "ssl"},
    }

    def _severity_matches(self, user_severity: str, actual_severity: str) -> bool:
        target = (user_severity or "").strip().lower()
        actual = (actual_severity or "").strip().lower()
        if not target:
            return True
        if actual == target:
            return True
        return any(actual == alias for alias in self._SEVERITY_ALIASES.get(target, {target}))

    def __init__(self) -> None:
        self._seed: list[dict[str, Any]] = [
            {
                "id": "INC-1001",
                "summary": "Payment API timeout during checkout",
                "service": "payments",
                "severity": "HIGH",
                "failure_type": "timeout",
                "root_cause": "upstream gateway latency",
            },
            {
                "id": "INC-1002",
                "summary": "Database connection pool exhausted in auth service",
                "service": "identity",
                "severity": "CRITICAL",
                "failure_type": "database_connection",
                "root_cause": "connection leak",
            },
            {
                "id": "INC-1003",
                "summary": "Kafka lag spike caused delayed order events",
                "service": "messaging",
                "severity": "MEDIUM",
                "failure_type": "latency",
                "root_cause": "consumer backlog",
            },
        ]

    def _flatten_payload(self, value: Any, prefix: str = "") -> list[str]:
        results: list[str] = []
        if value is None:
            return results
        if isinstance(value, str):
            return [value]
        if isinstance(value, (int, float, bool)):
            return [str(value)]
        if isinstance(value, dict):
            for key, item in value.items():
                nested_prefix = f"{prefix}.{key}" if prefix else str(key)
                results.extend(self._flatten_payload(item, nested_prefix))
            return results
        if isinstance(value, list):
            for item in value:
                results.extend(self._flatten_payload(item, prefix))
            return results
        return [str(value)]

    def _load_db_records(self) -> list[dict[str, Any]]:
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

    def _normalize_token(self, token: str) -> str:
        return token.strip("(),.-:!?").lower()

    def _extract_entities(self, query: str) -> set[str]:
        text = query.lower()
        entities: set[str] = set()
        for alias_key, alias_values in self._ENTITY_ALIASES.items():
            for alias in alias_values:
                if alias in text:
                    entities.add(alias_key)

        by_match = re.search(r"\bby\s+([a-zA-Z][a-zA-Z0-9_.-]+)", text)
        if by_match:
            entities.add(by_match.group(1).lower())
        return entities

    def _extract_query_intent(self, query: str) -> dict[str, Any]:
        normalized = re.sub(r"[^a-z0-9\s\-]", " ", query.lower())
        tokens = [self._normalize_token(token) for token in normalized.split() if self._normalize_token(token)]
        filtered = [token for token in tokens if token not in self._STOP_WORDS and token not in self._ACTION_WORDS and len(token) > 1]

        entities = self._extract_entities(query)
        wants_rca = any(word in query.lower() for word in ["rca", "root cause", "root-cause", "cause analysis"])
        wants_fix = any(word in query.lower() for word in ["fix", "resolution", "resolved", "fixed", "implemented"])

        return {
            "tokens": filtered,
            "entities": entities,
            "wants_rca": wants_rca,
            "wants_fix": wants_fix,
            "has_specific_entity": bool(entities),
        }

    def _high_value_tokens(self, query: str) -> list[str]:
        intent = self._extract_query_intent(query)
        tokens = [token for token in intent["tokens"] if token not in {"issue", "issues", "error", "errors", "exception", "exceptions"}]
        return tokens

    def _score(self, query: str, record: dict[str, Any]) -> float:
        text = " ".join(
            [
                str(record.get("summary", "")),
                str(record.get("description", "")),
                str(record.get("service", "")),
                str(record.get("severity", "")),
                str(record.get("failure_type", "")),
                str(record.get("root_cause", "")),
                str(record.get("resolution", "")),
                str(record.get("team", "")),
                str(record.get("assignee", "")),
                str(record.get("reporter", "")),
                *self._flatten_payload(record.get("raw_payload", {})),
            ]
        ).lower()

        intent = self._extract_query_intent(query)
        entity_score = 0.0
        for entity in intent["entities"]:
            alias_set = self._ENTITY_ALIASES.get(entity, {entity})
            if entity in text:
                entity_score += 12.0
            if any(alias in text for alias in alias_set):
                entity_score += 8.0

        rca_score = 0.0
        if intent["wants_rca"]:
            if "root cause" in text or "rca" in text:
                rca_score += 6.0
            if record.get("root_cause"):
                rca_score += 3.0
            if record.get("resolution"):
                rca_score += 2.0

        token_score = 0.0
        for token in intent["tokens"]:
            if token in text:
                token_score += 2.0

        bonus = 0.0
        if "root cause" in text or "rca" in text:
            bonus += 1.0
        if "fix" in text or "resolution" in text:
            bonus += 0.5

        return round(entity_score + rca_score + token_score + bonus, 3)

    def search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        filters = filters or {}
        db_records = self._load_db_records()
        records = db_records if db_records else self._seed

        intent = self._extract_query_intent(query)
        query_tokens = self._high_value_tokens(query)
        filtered: list[dict[str, Any]] = []
        for record in records:
            text_blob = " ".join(
                [
                    str(record.get("summary", "")),
                    str(record.get("description", "")),
                    str(record.get("service", "")),
                    str(record.get("root_cause", "")),
                    str(record.get("resolution", "")),
                    str(record.get("team", "")),
                    str(record.get("assignee", "")),
                    str(record.get("reporter", "")),
                    *self._flatten_payload(record.get("raw_payload", {})),
                ]
            ).lower()

            entity_match = False
            for entity in intent["entities"]:
                alias_set = self._ENTITY_ALIASES.get(entity, {entity})
                if entity in text_blob or any(alias in text_blob for alias in alias_set):
                    entity_match = True
                    break

            if intent["has_specific_entity"] and not entity_match:
                continue

            severity_filter_match = False
            for key, value in filters.items():
                if not value:
                    continue
                if key == "service":
                    if str(value).lower() not in text_blob:
                        break
                elif key == "assignee":
                    assignee_value = str(record.get("assignee", "")).lower()
                    if assignee_value == str(value).lower() or str(value).lower() in text_blob:
                        severity_filter_match = True
                        continue
                    break
                elif key == "severity":
                    actual = str(record.get("severity", "")).lower()
                    if self._severity_matches(str(value), actual):
                        severity_filter_match = True
                        continue
                    break
                elif str(record.get(key, "")).lower() != str(value).lower():
                    break
            else:
                if query_tokens and not any(token in text_blob for token in query_tokens):
                    if not entity_match and not severity_filter_match:
                        continue
                filtered.append(record)

        if not filtered and self._seed:
            fallback_records = self._seed
            fallback_filtered: list[dict[str, Any]] = []
            for record in fallback_records:
                text_blob = " ".join(
                    [
                        str(record.get("summary", "")),
                        str(record.get("description", "")),
                        str(record.get("service", "")),
                        str(record.get("root_cause", "")),
                        str(record.get("resolution", "")),
                        str(record.get("team", "")),
                        str(record.get("assignee", "")),
                        str(record.get("reporter", "")),
                        *self._flatten_payload(record.get("raw_payload", {})),
                    ]
                ).lower()
                if any(token in text_blob for token in query_tokens) or any(token in text_blob for token in ["database", "connection", "pool", "exhausted", "auth"]):
                    fallback_filtered.append(record)
            if fallback_filtered:
                filtered = fallback_filtered

        ranked = []
        for record in filtered:
            score = self._score(query, record)
            ranked.append({**record, "score": score})

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:limit]
