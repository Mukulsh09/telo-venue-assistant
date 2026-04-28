import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.document import DocumentStatus, DocumentType


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""

    title: str = Field(min_length=1, max_length=500, description="Document title")
    content: str = Field(min_length=1, description="Document text content")
    venue_id: uuid.UUID | None = Field(default=None, description="Associated venue ID")
    doc_type: DocumentType = Field(
        default=DocumentType.GENERAL, description="Document category"
    )
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class DocumentBulkCreate(BaseModel):
    """Schema for bulk document ingestion."""

    documents: list[DocumentCreate] = Field(
        min_length=1, max_length=100, description="List of documents to ingest"
    )


class DocumentResponse(BaseModel):
    """Schema for document in API responses."""

    id: uuid.UUID
    title: str
    content: str
    venue_id: uuid.UUID | None
    doc_type: DocumentType
    status: DocumentStatus
    metadata: dict
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Lightweight document response for list endpoints."""

    id: uuid.UUID
    title: str
    venue_id: uuid.UUID | None
    doc_type: DocumentType
    status: DocumentStatus
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IndexResponse(BaseModel):
    """Response after indexing a document."""

    document_id: uuid.UUID
    status: DocumentStatus
    chunks_created: int
    processing_time_ms: int