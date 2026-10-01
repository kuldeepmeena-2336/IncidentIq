from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="jira")
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    failure_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    dependency: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    missing_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="received")
    is_partial: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    team: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reporter: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
