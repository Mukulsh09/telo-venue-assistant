import uuid
from dataclasses import dataclass

from sqlalchemy import select, delete, text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk


@dataclass
class RetrievedChunk:
    """Represents a chunk returned from hybrid search with scores."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    metadata: dict
    similarity_score: float | None = None
    keyword_score: float | None = None
    combined_score: float = 0.0
    rank: int = 0


class ChunkRepository:
    """Handles all database operations for chunks, including vector search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_many(self, chunks: list[Chunk]) -> list[Chunk]:
        self.db.add_all(chunks)
        await self.db.flush()
        return chunks

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def count_by_document_id(self, document_id: uuid.UUID) -> int:
        stmt = select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Cosine similarity search via pgvector."""
        filters = []

        if metadata_filters:
            for key, value in metadata_filters.items():
                filters.append(
                    text(f"metadata->>'{key}' = :filter_{key}").bindparams(
                        **{f"filter_{key}": str(value)}
                    )
                )

        where_clause = and_(*filters) if filters else text("1=1")

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Chunk.metadata_.label("metadata"),
                (1 - Chunk.embedding.cosine_distance(query_embedding)).label(
                    "similarity"
                ),
            )
            .where(where_clause)
            .where(Chunk.embedding.isnot(None))
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(top_k * 2)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                metadata=row.metadata or {},
                similarity_score=float(row.similarity),
            )
            for row in rows
        ]

    async def keyword_search(
        self,
        query_text: str,
        top_k: int = 5,
        metadata_filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Full-text search via tsvector/tsquery."""
        filters = []

        if metadata_filters:
            for key, value in metadata_filters.items():
                filters.append(
                    text(f"metadata->>'{key}' = :filter_{key}").bindparams(
                        **{f"filter_{key}": str(value)}
                    )
                )

        where_clause = and_(*filters) if filters else text("1=1")

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Chunk.metadata_.label("metadata"),
                func.ts_rank(
                    Chunk.search_vector,
                    func.plainto_tsquery("english", query_text),
                ).label("rank_score"),
            )
            .where(where_clause)
            .where(
                Chunk.search_vector.op("@@")(
                    func.plainto_tsquery("english", query_text)
                )
            )
            .order_by(
                func.ts_rank(
                    Chunk.search_vector,
                    func.plainto_tsquery("english", query_text),
                ).desc()
            )
            .limit(top_k * 2)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                metadata=row.metadata or {},
                keyword_score=float(row.rank_score),
            )
            for row in rows
        ]