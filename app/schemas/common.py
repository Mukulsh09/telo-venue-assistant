from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""

    items: list[T]
    total: int = Field(description="Total number of records matching the query")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Number of items skipped")
    has_more: bool = Field(description="Whether more results exist beyond this page")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human readable error message")
    detail: str | None = Field(default=None, description="Additional error context")
    request_id: str | None = Field(default=None, description="Request tracking ID")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    version: str