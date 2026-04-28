import uuid
from datetime import datetime
from pydantic import BaseModel


class VenueResponse(BaseModel):
    """Schema for venue in API responses."""

    id: uuid.UUID
    name: str
    city: str
    neighborhood: str | None
    capacity: int | None
    price_per_head_usd: float | None
    venue_type: str | None
    amenities: list
    tags: list
    description: str | None
    policies: dict
    created_at: datetime

    model_config = {"from_attributes": True}