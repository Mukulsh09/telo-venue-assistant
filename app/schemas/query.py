import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Schema for asking a question."""

    question: str = Field(min_length=3, max_length=2000, description="The question to ask")
    filters: dict | None = Field(
        default=None,
        description="Optional metadata filters (e.g., city, venue_id, doc_type)",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class SourceReference(BaseModel):
    """A single source citation in the query response."""

    chunk_id: uuid.UUID | None
    document_title: str | None
    venue_name: str | None
    excerpt: str | None
    similarity_score: float | None
    keyword_score: float | None
    combined_score: float | None
    rank: int

    model_config = {"from_attributes": True}


class QueryResponse(BaseModel):
    """Full response to a question."""

    id: uuid.UUID
    question: str
    answer: str | None
    sources: list[SourceReference]
    confidence: str = Field(description="Confidence level: high, medium, low, none")
    confidence_score: float | None
    model_used: str | None
    retrieval_time_ms: int | None
    generation_time_ms: int | None
    total_time_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueryListResponse(BaseModel):
    """Lightweight query response for list/history endpoints."""

    id: uuid.UUID
    question: str
    confidence: str
    model_used: str | None
    total_time_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}