from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.settings import settings
from app.models.incident import Base, IncidentORM


class IncidentEmbeddingORM(Base):
    __tablename__ = "incident_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.id"), nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String(128), default="text-embedding-3-small")
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    incident: Mapped[IncidentORM] = relationship("IncidentORM", backref="embeddings")

    @property
    def vector_column_type(self) -> str:
        return "vector(1536)" if settings.database_url.startswith(("postgresql://", "postgres://")) else "text"
