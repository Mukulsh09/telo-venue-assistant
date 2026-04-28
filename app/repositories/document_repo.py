import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus, DocumentType


class DocumentRepository:
    """Handles all database operations for documents."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, document: Document) -> Document:
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def create_many(self, documents: list[Document]) -> list[Document]:
        self.db.add_all(documents)
        await self.db.flush()
        for doc in documents:
            await self.db.refresh(doc)
        return documents

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        stmt = select(Document).where(
            and_(Document.id == document_id, Document.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        limit: int = 20,
        offset: int = 0,
        status: DocumentStatus | None = None,
        doc_type: DocumentType | None = None,
        venue_id: uuid.UUID | None = None,
    ) -> tuple[list[Document], int]:
        """Returns (documents, total_count) with optional filters."""
        base_filter = Document.deleted_at.is_(None)
        filters = [base_filter]

        if status:
            filters.append(Document.status == status)
        if doc_type:
            filters.append(Document.doc_type == doc_type)
        if venue_id:
            filters.append(Document.venue_id == venue_id)

        count_stmt = select(func.count(Document.id)).where(and_(*filters))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Document)
            .where(and_(*filters))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        documents = list(result.scalars().all())

        return documents, total

    async def update_status(
        self, document_id: uuid.UUID, status: DocumentStatus, chunk_count: int = 0
    ) -> Document | None:
        doc = await self.get_by_id(document_id)
        if doc:
            doc.status = status
            doc.chunk_count = chunk_count
            await self.db.flush()
            await self.db.refresh(doc)
        return doc

    async def soft_delete(self, document_id: uuid.UUID) -> bool:
        doc = await self.get_by_id(document_id)
        if doc:
            doc.deleted_at = datetime.now(timezone.utc)
            await self.db.flush()
            return True
        return False