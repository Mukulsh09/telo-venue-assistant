import uuid
import pytest

from app.services.generation import build_context_prompt, parse_citations


class TestBuildContextPrompt:

    def test_builds_numbered_passages(self):
        passages = [
            {
                "content": "Harbor Loft allows outside catering.",
                "document_title": "Harbor Loft Policies",
                "venue_name": "Harbor Loft",
            },
            {
                "content": "Skyline Foundry does not allow outside catering.",
                "document_title": "Skyline Foundry FAQ",
                "venue_name": "Skyline Foundry",
            },
        ]
        prompt = build_context_prompt("Which venues allow catering?", passages)

        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "Harbor Loft Policies" in prompt
        assert "Skyline Foundry" in prompt

    def test_handles_empty_passages(self):
        prompt = build_context_prompt("Any question?", [])
        assert "Any question?" in prompt

    def test_handles_missing_metadata(self):
        passages = [{"content": "Some text", "document_title": "", "venue_name": ""}]
        prompt = build_context_prompt("Question?", passages)
        assert "[1]" in prompt
        assert "Some text" in prompt


class TestParseCitations:

    def test_parses_single_citation(self):
        assert parse_citations("The venue allows catering [1].") == [1]

    def test_parses_multiple_citations(self):
        assert parse_citations("Based on [1] and [3], confirmed [2].") == [1, 2, 3]

    def test_deduplicates_citations(self):
        assert parse_citations("As stated in [1], confirmed by [1].") == [1]

    def test_no_citations(self):
        assert parse_citations("I don't have enough information.") == []

    def test_handles_adjacent_citations(self):
        assert parse_citations("Multiple sources [1][2][3].") == [1, 2, 3]


class TestRetrievalConfidence:

    def _make_service(self):
        from app.services.retrieval import RetrievalService
        return RetrievalService(
            chunk_repo=None, embedding_provider=None,
            top_k=5, similarity_threshold=0.5, rrf_k=60,
        )

    def _make_chunk(self, similarity):
        from app.repositories.chunk_repo import RetrievedChunk
        return RetrievedChunk(
            chunk_id=uuid.uuid4(), document_id=uuid.uuid4(),
            content="test", metadata={}, similarity_score=similarity,
        )

    def test_high_confidence_single_strong_match(self):
        service = self._make_service()
        chunks = [self._make_chunk(0.92)]
        confidence, score = service._compute_confidence(chunks)
        assert confidence == "high"

    def test_high_confidence_multiple_good_matches(self):
        service = self._make_service()
        chunks = [self._make_chunk(0.80) for _ in range(4)]
        confidence, score = service._compute_confidence(chunks)
        assert confidence == "high"

    def test_medium_confidence(self):
        service = self._make_service()
        chunks = [self._make_chunk(0.70)]
        confidence, score = service._compute_confidence(chunks)
        assert confidence == "medium"

    def test_low_confidence(self):
        service = self._make_service()
        chunks = [self._make_chunk(0.55)]
        confidence, score = service._compute_confidence(chunks)
        assert confidence == "low"

    def test_no_confidence_below_threshold(self):
        service = self._make_service()
        chunks = [self._make_chunk(0.30)]
        confidence, score = service._compute_confidence(chunks)
        assert confidence == "none"

    def test_no_confidence_empty_chunks(self):
        service = self._make_service()
        confidence, score = service._compute_confidence([])
        assert confidence == "none"
        assert score == 0.0


class TestRRFFusion:

    def _make_service(self):
        from app.services.retrieval import RetrievalService
        return RetrievalService(
            chunk_repo=None, embedding_provider=None,
            top_k=5, similarity_threshold=0.5, rrf_k=60,
        )

    def test_fuses_overlapping_results(self):
        from app.repositories.chunk_repo import RetrievedChunk
        service = self._make_service()

        shared_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        semantic = [
            RetrievedChunk(chunk_id=shared_id, document_id=doc_id,
                           content="shared", metadata={}, similarity_score=0.9),
            RetrievedChunk(chunk_id=uuid.uuid4(), document_id=doc_id,
                           content="sem only", metadata={}, similarity_score=0.7),
        ]
        keyword = [
            RetrievedChunk(chunk_id=shared_id, document_id=doc_id,
                           content="shared", metadata={}, keyword_score=0.8),
            RetrievedChunk(chunk_id=uuid.uuid4(), document_id=doc_id,
                           content="kw only", metadata={}, keyword_score=0.6),
        ]

        fused = service._reciprocal_rank_fusion(semantic, keyword)
        assert str(fused[0].chunk_id) == str(shared_id)
        assert fused[0].combined_score > fused[1].combined_score

    def test_handles_empty_inputs(self):
        service = self._make_service()
        assert service._reciprocal_rank_fusion([], []) == []