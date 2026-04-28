import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue


class VenueRepository:
    """Handles read-only database operations for venues."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, venue_id: uuid.UUID) -> Venue | None:
        stmt = select(Venue).where(Venue.id == venue_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_venues(
        self, limit: int = 20, offset: int = 0
    ) -> tuple[list[Venue], int]:
        count_stmt = select(func.count(Venue.id))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Venue)
            .order_by(Venue.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        venues = list(result.scalars().all())

        return venues, total