import enum

from sqlalchemy import String, Integer, Text, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    FAQ = "faq"
    POLICY = "policy"
    OPERATIONAL_NOTE = "operational_note"
    BOOKING_DETAIL = "booking_detail"
    GENERAL = "general"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    venue_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type", create_type=True),
        nullable=False,
        default=DocumentType.GENERAL,
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=True),
        nullable=False,
        default=DocumentStatus.PENDING,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    venue = relationship("Venue", back_populates="documents", lazy="selectin")
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_documents_venue_id", "venue_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_doc_type", "doc_type"),
        Index(
            "ix_documents_not_deleted",
            "id",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"