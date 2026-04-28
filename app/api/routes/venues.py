import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status

from app.core.dependencies import get_venue_repo
from app.repositories.venue_repo import VenueRepository
from app.schemas.venue import VenueResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=PaginatedResponse[VenueResponse])
async def list_venues(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repo: VenueRepository = Depends(get_venue_repo),
):
    """List all venues with pagination."""
    venues, total = await repo.list_venues(limit=limit, offset=offset)

    return PaginatedResponse(
        items=[VenueResponse.model_validate(v) for v in venues],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{venue_id}", response_model=VenueResponse)
async def get_venue(
    venue_id: uuid.UUID,
    repo: VenueRepository = Depends(get_venue_repo),
):
    """Get a single venue by ID."""
    venue = await repo.get_by_id(venue_id)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue {venue_id} not found",
        )
    return VenueResponse.model_validate(venue)