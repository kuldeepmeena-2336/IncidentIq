from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from app.models.incident_embedding import IncidentEmbeddingORM
from app.services.database import SessionLocal


class VectorStoreService:
    _DEFAULT_VOCABULARY = [
        "payment", "payments", "checkout", "timeout", "gateway", "database", "db",
        "connection", "pool", "auth", "identity", "kafka", "lag", "order", "event",
        "latency", "slow", "api", "redis", "cache", "error", "failure", "incident",
    ]

    def build_text_embedding(self, text: str, vocabulary: list[str] | None = None) -> list[float]:
        vocab = vocabulary or self._DEFAULT_VOCABULARY
        token_counts = Counter(
            token
            for token in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
            if token
        )
        return [float(token_counts.get(token, 0)) for token in vocab]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        score = sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)
        return float(score)

    def save_embedding(self, incident_id: str, content: str, embedding: list[float], model: str = "heuristic-bag-of-words") -> dict[str, Any]:
        db = SessionLocal()
        try:
            record = IncidentEmbeddingORM(
                incident_id=incident_id,
                embedding_model=model,
                embedding_version="v1",
                content_hash=str(abs(hash(content))),
                vector_json=json.dumps(embedding),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return {"id": record.id, "incident_id": record.incident_id, "count": len(embedding)}
        finally:
            db.close()

    def search_similar_text(self, query: str, records: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        query_embedding = self.build_text_embedding(query or "")
        results: list[dict[str, Any]] = []

        for record in records:
            text = " ".join(
                [
                    str(record.get("summary", "")),
                    str(record.get("service", "")),
                    str(record.get("failure_type", "")),
                    str(record.get("root_cause", "")),
                ]
            )
            embedding = self.build_text_embedding(text)
            score = self._cosine_similarity(query_embedding, embedding)
            if score > 0.0 or any(token in text.lower() for token in (query or "").lower().split()):
                results.append({
                    "id": record.get("id"),
                    "summary": record.get("summary"),
                    "service": record.get("service"),
                    "severity": record.get("severity"),
                    "failure_type": record.get("failure_type"),
                    "score": round(score, 4),
                })

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def search_similar(self, query_embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(IncidentEmbeddingORM).all()
        finally:
            db.close()

        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                embedding = json.loads(row.vector_json or "[]")
            except Exception:
                continue
            if not embedding:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            results.append({"incident_id": row.incident_id, "score": float(score), "model": row.embedding_model})

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]
