from sqlalchemy import String, Integer, Float, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class QuerySource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "query_sources"

    query_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    keyword_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    query = relationship("Query", back_populates="sources")

    __table_args__ = (
        Index("ix_query_sources_query_id", "query_id"),
        Index("ix_query_sources_chunk_id", "chunk_id"),
    )

    def __repr__(self) -> str:
        return f"<QuerySource(query_id={self.query_id}, chunk_id={self.chunk_id}, rank={self.rank})>"