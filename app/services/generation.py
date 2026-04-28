import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a venue knowledge assistant for TeloHive. Your role is to answer
questions about venues based ONLY on the provided context passages.

Rules:
1. Answer ONLY based on the information in the provided context passages.
2. For each claim in your answer, cite which passage(s) support it using [1], [2], etc.
3. If the context does not contain enough information to answer the question,
   respond with: "I don't have enough information to answer this question."
4. Do NOT make up information or use knowledge outside the provided context.
5. Be concise and factual. Avoid speculation.
6. If multiple passages contain relevant information, synthesize them into a coherent answer."""


@dataclass
class GenerationResult:
    """Result from LLM answer generation."""

    answer: str
    cited_indices: list[int]
    model_used: str


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        """Generate a response given system and user prompts."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


class OpenAILLMProvider(LLMProvider):
    """OpenAI GPT provider for answer generation."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""

    def model_name(self) -> str:
        return self.model


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude provider for answer generation."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0,
            max_tokens=1024,
        )
        return response.content[0].text

    def model_name(self) -> str:
        return self.model


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory function to create the configured LLM provider."""
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )
    elif settings.llm_provider == "anthropic":
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def build_context_prompt(
    question: str, passages: list[dict]
) -> str:
    """Build the user prompt with numbered context passages."""
    context_parts = []
    for i, passage in enumerate(passages, 1):
        source_info = []
        if passage.get("document_title"):
            source_info.append(f"Source: {passage['document_title']}")
        if passage.get("venue_name"):
            source_info.append(f"Venue: {passage['venue_name']}")

        header = f"[{i}] ({', '.join(source_info)})" if source_info else f"[{i}]"
        context_parts.append(f"{header}\n{passage['content']}")

    context = "\n\n".join(context_parts)

    return f"""Context passages:
{context}

Question: {question}

Answer the question based only on the context passages above. Cite your sources using [1], [2], etc."""


def parse_citations(answer: str) -> list[int]:
    """Extract citation indices from the LLM answer."""
    matches = re.findall(r"\[(\d+)\]", answer)
    return sorted(set(int(m) for m in matches))