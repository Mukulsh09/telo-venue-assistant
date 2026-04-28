from sqlalchemy import String, Integer, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class Query(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "queries"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(10), nullable=False, default="none"
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieval_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sources = relationship(
        "QuerySource",
        back_populates="query",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Query(id={self.id}, confidence='{self.confidence}')>"