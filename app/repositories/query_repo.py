import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.query import Query
from app.models.query_source import QuerySource


class QueryRepository:
    """Handles database operations for query logs and their sources."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, query: Query, sources: list[QuerySource]) -> Query:
        self.db.add(query)
        await self.db.flush()

        for source in sources:
            source.query_id = query.id
            self.db.add(source)

        await self.db.flush()
        await self.db.refresh(query)
        return query

    async def get_by_id(self, query_id: uuid.UUID) -> Query | None:
        stmt = (
            select(Query)
            .options(selectinload(Query.sources))
            .where(Query.id == query_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()