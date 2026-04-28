from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TextChunk:
    """Represents a single chunk of text from a document."""

    content: str
    chunk_index: int
    token_count: int


class ChunkingService:
    """Splits document text into overlapping chunks for embedding."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[TextChunk]:
        """
        Split text into chunks using character-based splitting with overlap.

        For short documents (under chunk_size), returns the full text as a
        single chunk. For longer documents, splits on word boundaries
        with configurable overlap to preserve context.
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # Approximate tokens as words (rough but consistent)
        words = text.split()
        total_words = len(words)

        if total_words <= self.chunk_size:
            return [
                TextChunk(content=text, chunk_index=0, token_count=total_words)
            ]

        chunks = []
        start = 0
        chunk_index = 0

        while start < total_words:
            end = min(start + self.chunk_size, total_words)
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunks.append(
                TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    token_count=len(chunk_words),
                )
            )

            if end >= total_words:
                break

            start = end - self.chunk_overlap
            chunk_index += 1

        logger.info(
            "chunking_complete",
            total_words=total_words,
            chunks_created=len(chunks),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        return chunks