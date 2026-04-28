import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status

from app.core.dependencies import get_document_repo, get_ingestion_service
from app.models.document import Document, DocumentStatus, DocumentType
from app.repositories.document_repo import DocumentRepository
from app.services.ingestion import IngestionService
from app.schemas.document import (
    DocumentCreate,
    DocumentBulkCreate,
    DocumentResponse,
    DocumentListResponse,
    IndexResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Ingest a new document into the system."""
    document = Document(
        title=payload.title,
        content=payload.content,
        venue_id=payload.venue_id,
        doc_type=payload.doc_type,
        metadata_=payload.metadata,
        status=DocumentStatus.PENDING,
    )
    created = await repo.create(document)
    return _to_response(created)


@router.post(
    "/bulk",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_documents_bulk(
    payload: DocumentBulkCreate,
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Ingest multiple documents in a single request."""
    documents = [
        Document(
            title=doc.title,
            content=doc.content,
            venue_id=doc.venue_id,
            doc_type=doc.doc_type,
            metadata_=doc.metadata,
            status=DocumentStatus.PENDING,
        )
        for doc in payload.documents
    ]
    created = await repo.create_many(documents)
    return [_to_response(d) for d in created]


@router.get("", response_model=PaginatedResponse[DocumentListResponse])
async def list_documents(
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
    status_filter: DocumentStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    doc_type: DocumentType | None = Query(
        default=None, description="Filter by document type"
    ),
    venue_id: uuid.UUID | None = Query(
        default=None, description="Filter by venue ID"
    ),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """List documents with pagination and optional filters."""
    documents, total = await repo.list_documents(
        limit=limit,
        offset=offset,
        status=status_filter,
        doc_type=doc_type,
        venue_id=venue_id,
    )

    return PaginatedResponse(
        items=[_to_list_response(d) for d in documents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Get a single document by ID."""
    document = await repo.get_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return _to_response(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Soft delete a document and its associated chunks."""
    deleted = await repo.soft_delete(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )


@router.post("/{document_id}/index", response_model=IndexResponse)
async def index_document(
    document_id: uuid.UUID,
    ingestion: IngestionService = Depends(get_ingestion_service),
):
    """Trigger chunking and embedding for a document."""
    try:
        result = await ingestion.index_document(document_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Indexing failed: {str(e)}",
        )

    return IndexResponse(
        document_id=result["document_id"],
        status=DocumentStatus.INDEXED,
        chunks_created=result["chunks_created"],
        processing_time_ms=result["processing_time_ms"],
    )


def _to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        venue_id=doc.venue_id,
        doc_type=doc.doc_type,
        status=doc.status,
        metadata=doc.metadata_,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _to_list_response(doc: Document) -> DocumentListResponse:
    return DocumentListResponse(
        id=doc.id,
        title=doc.title,
        venue_id=doc.venue_id,
        doc_type=doc.doc_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )