from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings, Settings
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.venue_repo import VenueRepository
from app.repositories.query_repo import QueryRepository
from app.services.chunking import ChunkingService
from app.services.embedding import get_embedding_provider, EmbeddingProvider
from app.services.generation import get_llm_provider, LLMProvider
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


def get_document_repo(db: AsyncSession = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(db)


def get_chunk_repo(db: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(db)


def get_venue_repo(db: AsyncSession = Depends(get_db)) -> VenueRepository:
    return VenueRepository(db)


def get_query_repo(db: AsyncSession = Depends(get_db)) -> QueryRepository:
    return QueryRepository(db)


def get_chunking_service(settings: Settings = Depends(get_settings)) -> ChunkingService:
    return ChunkingService(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def get_embedding_service(settings: Settings = Depends(get_settings)) -> EmbeddingProvider:
    return get_embedding_provider(settings)


def get_llm_service(settings: Settings = Depends(get_settings)) -> LLMProvider:
    return get_llm_provider(settings)


def get_ingestion_service(
    document_repo: DocumentRepository = Depends(get_document_repo),
    chunk_repo: ChunkRepository = Depends(get_chunk_repo),
    chunking_service: ChunkingService = Depends(get_chunking_service),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_service),
) -> IngestionService:
    return IngestionService(
        document_repo=document_repo,
        chunk_repo=chunk_repo,
        chunking_service=chunking_service,
        embedding_provider=embedding_provider,
    )


def get_retrieval_service(
    chunk_repo: ChunkRepository = Depends(get_chunk_repo),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_service),
    settings: Settings = Depends(get_settings),
) -> RetrievalService:
    return RetrievalService(
        chunk_repo=chunk_repo,
        embedding_provider=embedding_provider,
        top_k=settings.retrieval_top_k,
        similarity_threshold=settings.similarity_threshold,
        rrf_k=settings.rrf_k,
    )