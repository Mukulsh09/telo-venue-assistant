import time
from dataclasses import dataclass

from app.core.logging import get_logger
from app.repositories.chunk_repo import ChunkRepository, RetrievedChunk
from app.services.embedding import EmbeddingProvider

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """Result from the hybrid retrieval pipeline."""

    chunks: list[RetrievedChunk]
    confidence: str
    confidence_score: float
    retrieval_time_ms: int


class RetrievalService:
    """
    Hybrid retrieval combining semantic search (pgvector) and keyword
    search (tsvector) using Reciprocal Rank Fusion (RRF).

    RRF merges ranked lists without requiring score normalization:
        combined_score = 1/(k + semantic_rank) + 1/(k + keyword_rank)
    where k=60 is the standard constant.
    """

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        embedding_provider: EmbeddingProvider,
        top_k: int = 5,
        similarity_threshold: float = 0.5,
        rrf_k: int = 60,
    ):
        self.chunk_repo = chunk_repo
        self.embedding_provider = embedding_provider
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        question: str,
        top_k: int | None = None,
        metadata_filters: dict | None = None,
    ) -> RetrievalResult:
        """
        Execute hybrid retrieval:
        1. Embed the question
        2. Run semantic search (pgvector cosine similarity)
        3. Run keyword search (tsvector ts_rank)
        4. Fuse results using RRF
        5. Compute confidence based on top scores
        """
        start_time = time.time()
        k = top_k or self.top_k

        # Step 1: Embed the query
        query_embeddings = await self.embedding_provider.embed([question])
        query_embedding = query_embeddings[0]

        # Step 2: Semantic search
        semantic_results = await self.chunk_repo.semantic_search(
            query_embedding=query_embedding,
            top_k=k,
            metadata_filters=metadata_filters,
        )

        # Step 3: Keyword search
        keyword_results = await self.chunk_repo.keyword_search(
            query_text=question,
            top_k=k,
            metadata_filters=metadata_filters,
        )

        # Step 4: Fuse with RRF
        fused = self._reciprocal_rank_fusion(semantic_results, keyword_results)

        # Step 5: Take top K and compute confidence
        top_chunks = fused[:k]

        for i, chunk in enumerate(top_chunks):
            chunk.rank = i + 1

        confidence, confidence_score = self._compute_confidence(top_chunks)

        retrieval_time = int((time.time() - start_time) * 1000)

        logger.info(
            "retrieval_complete",
            question_length=len(question),
            semantic_hits=len(semantic_results),
            keyword_hits=len(keyword_results),
            fused_results=len(fused),
            top_k_returned=len(top_chunks),
            confidence=confidence,
            retrieval_time_ms=retrieval_time,
        )

        return RetrievalResult(
            chunks=top_chunks,
            confidence=confidence,
            confidence_score=confidence_score,
            retrieval_time_ms=retrieval_time,
        )

    def _reciprocal_rank_fusion(
        self,
        semantic_results: list[RetrievedChunk],
        keyword_results: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """
        Merge two ranked lists using Reciprocal Rank Fusion.

        RRF is rank-based (not score-based), so it works without
        normalizing the different score ranges from semantic and keyword search.
        """
        chunk_map: dict[str, RetrievedChunk] = {}
        rrf_scores: dict[str, float] = {}

        # Score from semantic results
        for rank, chunk in enumerate(semantic_results, start=1):
            key = str(chunk.chunk_id)
            chunk_map[key] = chunk
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (self.rrf_k + rank)

        # Score from keyword results
        for rank, chunk in enumerate(keyword_results, start=1):
            key = str(chunk.chunk_id)
            if key not in chunk_map:
                chunk_map[key] = chunk
            else:
                # Merge keyword score into existing chunk
                chunk_map[key].keyword_score = chunk.keyword_score
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (self.rrf_k + rank)

        # Sort by combined RRF score descending
        sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)

        fused = []
        for key in sorted_keys:
            chunk = chunk_map[key]
            chunk.combined_score = rrf_scores[key]
            fused.append(chunk)

        return fused

    def _compute_confidence(
        self, chunks: list[RetrievedChunk]
    ) -> tuple[str, float]:
        """
        Compute confidence level based on retrieval quality.

        HIGH: top chunk similarity > 0.85 OR 3+ chunks with similarity > 0.75
        MEDIUM: top chunk similarity between 0.6 and 0.85
        LOW: top chunk similarity between 0.5 and 0.6
        NONE: no chunks or top similarity < 0.5
        """
        if not chunks:
            return "none", 0.0

        top_similarity = chunks[0].similarity_score or 0.0
        high_quality_count = sum(
            1
            for c in chunks
            if (c.similarity_score or 0) > 0.75
        )

        if top_similarity > 0.85 or high_quality_count >= 3:
            return "high", top_similarity
        elif top_similarity >= 0.6:
            return "medium", top_similarity
        elif top_similarity >= self.similarity_threshold:
            return "low", top_similarity
        else:
            return "none", top_similarity