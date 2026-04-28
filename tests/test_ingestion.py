import pytest

from app.services.chunking import ChunkingService


class TestChunkingService:
    """Unit tests for the chunking service."""

    def test_empty_text_returns_no_chunks(self):
        service = ChunkingService(chunk_size=100, chunk_overlap=10)
        chunks = service.chunk_text("")
        assert chunks == []

    def test_whitespace_text_returns_no_chunks(self):
        service = ChunkingService(chunk_size=100, chunk_overlap=10)
        chunks = service.chunk_text("   \n\t  ")
        assert chunks == []

    def test_short_text_returns_single_chunk(self):
        service = ChunkingService(chunk_size=100, chunk_overlap=10)
        text = "This is a short document about venue policies."
        chunks = service.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == text
        assert chunks[0].token_count == len(text.split())

    def test_long_text_creates_multiple_chunks(self):
        service = ChunkingService(chunk_size=10, chunk_overlap=2)
        words = [f"word{i}" for i in range(30)]
        text = " ".join(words)

        chunks = service.chunk_text(text)

        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_overlap_preserves_context(self):
        service = ChunkingService(chunk_size=10, chunk_overlap=3)
        words = [f"w{i}" for i in range(25)]
        text = " ".join(words)

        chunks = service.chunk_text(text)

        assert len(chunks) >= 2
        first_chunk_words = chunks[0].content.split()
        second_chunk_words = chunks[1].content.split()
        overlap_words = first_chunk_words[-3:]
        assert overlap_words == second_chunk_words[:3]

    def test_chunk_size_respected(self):
        service = ChunkingService(chunk_size=10, chunk_overlap=2)
        words = [f"word{i}" for i in range(50)]
        text = " ".join(words)

        chunks = service.chunk_text(text)

        for chunk in chunks:
            assert chunk.token_count <= 10

    def test_configurable_parameters(self):
        service = ChunkingService(chunk_size=5, chunk_overlap=1)
        text = "one two three four five six seven eight nine ten"

        chunks = service.chunk_text(text)

        assert len(chunks) >= 2
        assert chunks[0].token_count == 5