from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings
from app.models.incident import Base, IncidentORM


def _is_postgres() -> bool:
    return settings.database_url.startswith(("postgresql://", "postgres://"))


def _ensure_schema_columns() -> None:
    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            if not inspector.has_table("incidents"):
                return
            columns = {col["name"] for col in inspector.get_columns("incidents")}
            for column_name, statement in {
                "team": "ALTER TABLE incidents ADD COLUMN team VARCHAR(128)",
                "assignee": "ALTER TABLE incidents ADD COLUMN assignee VARCHAR(128)",
                "reporter": "ALTER TABLE incidents ADD COLUMN reporter VARCHAR(128)",
            }.items():
                if column_name not in columns:
                    conn.execute(text(statement))
    except Exception:
        pass


engine = create_engine(settings.database_url, echo=False, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    if _is_postgres():
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_incident(db: Session, incident: dict[str, Any]) -> dict[str, Any]:
    incident_id = incident.get("id") or incident.get("external_id") or "incident-unknown"
    record = db.query(IncidentORM).filter(IncidentORM.external_id == incident.get("external_id")).first()
    if record is None:
        record = IncidentORM(id=str(incident_id))
        db.add(record)

    record.source = incident.get("source", record.source or "jira")
    record.external_id = incident.get("external_id") or record.external_id
    record.summary = incident.get("summary") or record.summary
    record.description = incident.get("description") or record.description
    record.service = incident.get("service") or record.service
    record.severity = incident.get("severity") or record.severity or "MEDIUM"
    record.failure_type = incident.get("failure_type") or record.failure_type
    record.dependency = incident.get("dependency") or record.dependency
    record.root_cause = incident.get("root_cause") or record.root_cause
    record.resolution = incident.get("resolution") or record.resolution
    record.team = incident.get("team") or record.team
    record.assignee = incident.get("assignee") or record.assignee
    record.reporter = incident.get("reporter") or record.reporter
    record.raw_payload = incident.get("raw_payload") or record.raw_payload
    record.confidence = float(incident.get("confidence") or record.confidence or 0.0)
    record.missing_fields = incident.get("missing_fields") or record.missing_fields or []
    record.completeness = float(incident.get("completeness") or record.completeness or 0.0)
    record.status = incident.get("status") or record.status or "received"
    record.is_partial = bool(incident.get("is_partial") or bool(record.missing_fields))
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "status": record.status,
        "severity": record.severity,
        "confidence": record.confidence,
        "partial": record.is_partial,
    }
