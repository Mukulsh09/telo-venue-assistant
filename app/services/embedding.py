from abc import ABC, abstractmethod

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers. Swap implementations via config."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension for this provider."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small provider (1536 dimensions)."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._dimension = 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Process in batches of 100 to respect API limits
        all_embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self.client.embeddings.create(
                model=self.model, input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.info(
                "embeddings_generated",
                batch_index=i // batch_size,
                batch_size=len(batch),
                model=self.model,
            )

        return all_embeddings

    def dimension(self) -> int:
        return self._dimension

    def model_name(self) -> str:
        return self.model


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Local HuggingFace all-MiniLM-L6-v2 provider (384 dimensions)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._dimension = 384
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        self._load_model()
        embeddings = self._model.encode(texts, show_progress_bar=False)

        logger.info(
            "embeddings_generated",
            count=len(texts),
            model=self._model_name,
        )

        return [embedding.tolist() for embedding in embeddings]

    def dimension(self) -> int:
        return self._dimension

    def model_name(self) -> str:
        return self._model_name


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Factory function to create the configured embedding provider."""
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
    elif settings.embedding_provider == "huggingface":
        return HuggingFaceEmbeddingProvider()
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")