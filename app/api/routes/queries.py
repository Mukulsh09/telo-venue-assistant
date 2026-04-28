import uuid
import time

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.core.dependencies import (
    get_query_repo,
    get_retrieval_service,
    get_llm_service,
)
from app.core.config import get_settings
from app.models.query import Query
from app.models.query_source import QuerySource
from app.repositories.query_repo import QueryRepository
from app.services.retrieval import RetrievalService
from app.services.generation import (
    LLMProvider,
    SYSTEM_PROMPT,
    build_context_prompt,
    parse_citations,
)
from app.schemas.query import QueryRequest, QueryResponse, SourceReference

router = APIRouter(prefix="/query", tags=["queries"])


@router.post("", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    payload: QueryRequest,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    llm: LLMProvider = Depends(get_llm_service),
    query_repo: QueryRepository = Depends(get_query_repo),
):
    """
    Ask a question over indexed venue documents.

    The system retrieves relevant passages using hybrid search (semantic + keyword),
    then generates a grounded answer with citations. If confidence is too low,
    it returns the raw passages without LLM generation to avoid hallucination.
    """
    total_start = time.time()
    settings = get_settings()

    # Step 1: Retrieve relevant chunks
    retrieval_result = await retrieval.retrieve(
        question=payload.question,
        top_k=payload.top_k,
        metadata_filters=payload.filters,
    )

    # Step 2: Decide whether to generate an answer
    answer = None
    generation_time_ms = None
    model_used = None

    if retrieval_result.confidence == "none" or not retrieval_result.chunks:
        answer = "I don't have enough information to answer this question based on the available documents."
        model_used = None
    else:
        # Build context and generate answer via LLM
        passages = [
            {
                "content": chunk.content,
                "document_title": chunk.metadata.get("document_title", ""),
                "venue_name": chunk.metadata.get("venue_name", ""),
            }
            for chunk in retrieval_result.chunks
        ]

        user_prompt = build_context_prompt(payload.question, passages)

        gen_start = time.time()
        try:
            answer = await llm.generate(SYSTEM_PROMPT, user_prompt)
            model_used = llm.model_name()
        except Exception as e:
            # LLM failure: return raw passages instead of crashing
            answer = (
                "Unable to generate a synthesized answer (LLM service unavailable). "
                "Relevant passages are included in the sources below."
            )
            model_used = None
        generation_time_ms = int((time.time() - gen_start) * 1000)

    total_time_ms = int((time.time() - total_start) * 1000)

    # Step 3: Build source references
    source_records = []
    for chunk in retrieval_result.chunks:
        source = QuerySource(
            chunk_id=chunk.chunk_id,
            document_title=chunk.metadata.get("document_title"),
            venue_name=chunk.metadata.get("venue_name"),
            excerpt=chunk.content,
            similarity_score=chunk.similarity_score,
            keyword_score=chunk.keyword_score,
            combined_score=chunk.combined_score,
            rank=chunk.rank,
        )
        source_records.append(source)

    # Step 4: Save query log
    query_record = Query(
        question=payload.question,
        answer=answer,
        confidence=retrieval_result.confidence,
        confidence_score=retrieval_result.confidence_score,
        model_used=model_used,
        metadata_filters=payload.filters,
        retrieval_time_ms=retrieval_result.retrieval_time_ms,
        generation_time_ms=generation_time_ms,
        total_time_ms=total_time_ms,
    )

    saved_query = await query_repo.create(query_record, source_records)

    # Step 5: Build response
    return QueryResponse(
        id=saved_query.id,
        question=saved_query.question,
        answer=saved_query.answer,
        sources=[
            SourceReference(
                chunk_id=s.chunk_id,
                document_title=s.document_title,
                venue_name=s.venue_name,
                excerpt=s.excerpt,
                similarity_score=s.similarity_score,
                keyword_score=s.keyword_score,
                combined_score=s.combined_score,
                rank=s.rank,
            )
            for s in source_records
        ],
        confidence=saved_query.confidence,
        confidence_score=saved_query.confidence_score,
        model_used=saved_query.model_used,
        retrieval_time_ms=saved_query.retrieval_time_ms,
        generation_time_ms=saved_query.generation_time_ms,
        total_time_ms=saved_query.total_time_ms,
        created_at=saved_query.created_at,
    )


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: uuid.UUID,
    query_repo: QueryRepository = Depends(get_query_repo),
):
    """Retrieve a past query and its full response with sources."""
    query = await query_repo.get_by_id(query_id)
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query {query_id} not found",
        )

    return QueryResponse(
        id=query.id,
        question=query.question,
        answer=query.answer,
        sources=[
            SourceReference(
                chunk_id=s.chunk_id,
                document_title=s.document_title,
                venue_name=s.venue_name,
                excerpt=s.excerpt,
                similarity_score=s.similarity_score,
                keyword_score=s.keyword_score,
                combined_score=s.combined_score,
                rank=s.rank,
            )
            for s in query.sources
        ],
        confidence=query.confidence,
        confidence_score=query.confidence_score,
        model_used=query.model_used,
        retrieval_time_ms=query.retrieval_time_ms,
        generation_time_ms=query.generation_time_ms,
        total_time_ms=query.total_time_ms,
        created_at=query.created_at,
    )