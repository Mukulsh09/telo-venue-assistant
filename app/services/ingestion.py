import uuid
import time

from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import ChunkRepository
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingProvider

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates the document ingestion pipeline: chunk, embed, store."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        chunking_service: ChunkingService,
        embedding_provider: EmbeddingProvider,
    ):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.chunking_service = chunking_service
        self.embedding_provider = embedding_provider

    async def index_document(self, document_id: uuid.UUID) -> dict:
        """
        Full indexing pipeline for a single document:
        1. Validate document exists and is not already indexing
        2. Split content into chunks
        3. Generate embeddings for each chunk
        4. Store chunks with embeddings and metadata
        5. Update document status

        Returns a summary dict with chunks_created and processing_time_ms.
        """
        start_time = time.time()

        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        if document.status == DocumentStatus.INDEXING:
            raise ValueError(f"Document {document_id} is already being indexed")

        # Mark as indexing
        await self.document_repo.update_status(document_id, DocumentStatus.INDEXING)

        try:
            # Remove existing chunks if re-indexing
            await self.chunk_repo.delete_by_document_id(document_id)

            # Step 1: Chunk the document
            text_chunks = self.chunking_service.chunk_text(document.content)

            if not text_chunks:
                await self.document_repo.update_status(
                    document_id, DocumentStatus.INDEXED, chunk_count=0
                )
                return {
                    "document_id": document_id,
                    "chunks_created": 0,
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                }

            # Step 2: Generate embeddings
            chunk_texts = [chunk.content for chunk in text_chunks]
            embeddings = await self.embedding_provider.embed(chunk_texts)

            # Step 3: Build chunk metadata (denormalized from document)
            chunk_metadata = self._build_chunk_metadata(document)

            # Step 4: Create and store chunk records
            chunk_records = []
            for text_chunk, embedding in zip(text_chunks, embeddings):
                chunk = Chunk(
                    document_id=document_id,
                    chunk_index=text_chunk.chunk_index,
                    content=text_chunk.content,
                    embedding=embedding,
                    token_count=text_chunk.token_count,
                    metadata_=chunk_metadata,
                )
                chunk_records.append(chunk)

            await self.chunk_repo.create_many(chunk_records)

            # Step 5: Update document status
            await self.document_repo.update_status(
                document_id, DocumentStatus.INDEXED, chunk_count=len(chunk_records)
            )

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "document_indexed",
                document_id=str(document_id),
                chunks_created=len(chunk_records),
                processing_time_ms=processing_time,
            )

            return {
                "document_id": document_id,
                "chunks_created": len(chunk_records),
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            await self.document_repo.update_status(
                document_id, DocumentStatus.FAILED
            )
            logger.error(
                "indexing_failed",
                document_id=str(document_id),
                error=str(e),
            )
            raise

    def _build_chunk_metadata(self, document: Document) -> dict:
        """Build denormalized metadata for chunk-level filtering."""
        metadata = {
            "doc_type": document.doc_type.value if document.doc_type else None,
        }

        if document.venue_id:
            metadata["venue_id"] = str(document.venue_id)

        if document.venue:
            metadata["venue_name"] = document.venue.name
            metadata["city"] = document.venue.city

        return metadata