from sqlalchemy import String, Integer, Text, ForeignKey, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.core.config import get_settings
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class Chunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chunks"

    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(
        Vector(get_settings().embedding_dimension), nullable=True
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )

    document = relationship("Document", back_populates="chunks", lazy="selectin")

    __table_args__ = (
        Index("ix_chunks_document_id", "document_id"),
        Index(
            "ix_chunks_document_chunk",
            "document_id",
            "chunk_index",
            unique=True,
        ),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_chunks_metadata", "metadata", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"