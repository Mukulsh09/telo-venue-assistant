# RAG Powered Venue Knowledge Assistant API

A backend system for internal knowledge retrieval over venue documents and operational notes. Built for the TeloHive Backend Co-op Assessment (Task 2).

## Problem Summary

TeloHive's operations teams need fast, trustworthy answers about venue policies, capabilities, and logistics. Rather than manually searching through FAQs, policy documents, and operational notes, this system lets internal users ask natural language questions and receive grounded answers with source citations.

This is a knowledge retrieval problem where accuracy and traceability matter more than conversational flair. Every answer must be traceable to specific source documents, and the system should say "I don't have enough information" rather than hallucinate.

**Assumptions:**
- Documents are relatively short (under 2000 tokens) based on the sample data, so a simple chunking strategy with overlap suffices
- This is an internal tool, not a consumer facing chatbot, so reliability matters more than response creativity
- The system should support multiple embedding and LLM providers to avoid vendor lock in

## Architecture Overview

The system has three layers:

1. **Ingestion pipeline** accepts documents, splits them into overlapping chunks, generates embeddings via OpenAI, and stores everything in PostgreSQL with pgvector.

2. **Storage layer** uses PostgreSQL for both structured data and vector search. Chunks have a pgvector column for semantic search and a tsvector column for keyword search, enabling true hybrid retrieval in a single database.

3. **Query pipeline** embeds the user's question, runs hybrid retrieval (semantic + keyword with Reciprocal Rank Fusion), then sends retrieved passages to an LLM with a grounding prompt that enforces citation and prevents hallucination.

```
  Ingest Flow:
  ─────────────
  POST /documents ──► Chunking Service ──► Embedding (OpenAI) ──► PostgreSQL + pgvector

  Query Flow:
  ──────────
  POST /query ──► Embed Question ──► Hybrid Retrieval ──► GPT-4o-mini (grounded) ──► Answer + Citations
                                      (Semantic + Keyword)
                                      (RRF Fusion)
```

**Data Flow:** Ingest document → chunk text → generate embeddings → store in pgvector → query embeds question → hybrid retrieval (semantic + keyword) → LLM generates grounded answer with citations → response with sources

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Embeddings | OpenAI text-embedding-3-small (1536d) |
| LLM | OpenAI GPT-4o-mini (swappable to Claude) |
| Containerization | Docker Compose |
| Testing | pytest + httpx (async) |
| Logging | structlog (JSON) |

## Local Setup

### Prerequisites
- Docker and Docker Compose
- An OpenAI API key (for embeddings and answer generation)

### Steps

1. Clone the repository:
```bash
git clone https://github.com/Mukulsh09/telo-venue-assistant.git
cd telo-venue-assistant
```

2. Create your environment file:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. Start the services:
```bash
docker-compose up --build -d
```

4. Create database tables:

Due to a known SQLAlchemy/Alembic ENUM interaction (see Known Limitations), tables are created via the async engine:
```bash
docker-compose exec db psql -U telo -d telo_venue_assistant -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker-compose exec app python -c "
import asyncio
from app.core.database import engine, Base
from app.models.venue import Venue
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.query import Query
from app.models.query_source import QuerySource

async def create():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created.')

asyncio.run(create())
"
```

5. Seed sample data:
```bash
docker-compose exec app python -m scripts.seed
```

6. Index all documents (generates embeddings):
```bash
# Get document IDs
curl http://localhost:8000/api/v1/documents | python3 -m json.tool

# Index each document (replace with actual IDs from above)
curl -X POST http://localhost:8000/api/v1/documents/{document_id}/index
```

7. The API is now running at `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/api/v1/health`

## How to Run Tests

```bash
docker-compose exec app pytest tests/ -v
```

Tests cover document CRUD, ingestion pipeline, query validation, and edge cases. Note: integration tests that call the OpenAI API require a valid API key in `.env`.

## API Endpoint Summary

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents` | Ingest a single document |
| POST | `/api/v1/documents/bulk` | Ingest multiple documents |
| GET | `/api/v1/documents` | List documents (paginated, filterable) |
| GET | `/api/v1/documents/{id}` | Get document details |
| DELETE | `/api/v1/documents/{id}` | Soft delete a document |
| POST | `/api/v1/documents/{id}/index` | Trigger chunking and embedding |

### Queries

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query` | Ask a question with optional filters |
| GET | `/api/v1/query/{id}` | Retrieve a past query with sources |

### Venues and System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/venues` | List venues (paginated) |
| GET | `/api/v1/venues/{id}` | Get venue details |
| GET | `/api/v1/health` | Health check with DB status |

### Example: Ingest and Query

```bash
# 1. Create a document
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Harbor Loft Policies",
    "content": "Harbor Loft allows outside catering with prior approval.",
    "doc_type": "policy"
  }'

# 2. Index the document (replace DOCUMENT_ID with the id from step 1)
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/index

# 3. Ask a question
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which venues allow outside catering?", "top_k": 5}'
```

### Example: Query Response

```json
{
  "id": "349e99be-e871-4f6d-b717-aa455d5b03e3",
  "question": "Which venues allow outside catering?",
  "answer": "The venue that allows outside catering is Harbor Loft, which permits it with prior approval [1]. Skyline Foundry does not allow outside catering [2].",
  "sources": [
    {
      "chunk_id": "5101827d-...",
      "venue_name": "Harbor Loft",
      "excerpt": "Harbor Loft allows outside catering with prior approval...",
      "similarity_score": 0.574,
      "keyword_score": 0.438,
      "combined_score": 0.033,
      "rank": 1
    }
  ],
  "confidence": "low",
  "confidence_score": 0.574,
  "model_used": "gpt-4o-mini",
  "retrieval_time_ms": 2162,
  "generation_time_ms": 3192,
  "total_time_ms": 5355
}
```

## Design Decisions

### 1. pgvector over FAISS or ChromaDB

pgvector keeps vectors in the same PostgreSQL database as structured data. This means hybrid queries (SQL metadata filters + cosine similarity) run in a single query with no cross-system synchronization. For a production system, this eliminates an entire class of consistency bugs and simplifies backup, replication, and monitoring.

### 2. True hybrid search with Reciprocal Rank Fusion

The system runs two parallel searches: semantic (pgvector cosine similarity on embeddings) and keyword (PostgreSQL tsvector/tsquery full text search). Results are merged using Reciprocal Rank Fusion (RRF), which combines ranked lists without requiring score normalization. Chunks that appear in both result sets get boosted, catching cases where semantic search misses an exact keyword match or keyword search misses a semantically similar passage.

### 3. PostgreSQL ENUMs for status and doc_type

Database level validation (not just API level) prevents invalid states. The `indexing` status enables detection and recovery from partial embedding failures.

### 4. Provider abstraction (Strategy Pattern)

Both the embedding service and LLM generation service use an abstract base class with concrete implementations for OpenAI and an alternative (HuggingFace for embeddings, Anthropic Claude for generation). Swapping providers is a single environment variable change (`EMBEDDING_PROVIDER`, `LLM_PROVIDER`).

### 5. Junction table for query sources

Every query is logged with its answer, sources, confidence, and timing metrics. The sources are stored in a proper `query_sources` junction table (not a JSONB blob) so that analytics queries like "most cited chunks" or "documents with zero citations" are straightforward SQL.

### 6. Denormalized metadata on chunks

Each chunk stores denormalized metadata (venue_id, city, doc_type, venue_name) copied from its parent document. This trades a small amount of write time duplication for significant read time speed during retrieval, avoiding JOINs on the hot path.

### 7. Soft delete for documents

Documents are soft deleted (a `deleted_at` timestamp is set) rather than hard deleted. This is standard practice for production systems where accidental deletions happen and audit trails matter.

### 8. Confidence tiers and the no answer path

The system scores confidence as high/medium/low/none based on retrieval similarity. If the best matching chunk has similarity below 0.5, the system returns "I don't have enough information" without calling the LLM. This prevents hallucination from weak context and saves unnecessary LLM API costs.

### 9. tsvector GENERATED ALWAYS

The `search_vector` column on chunks is auto maintained by PostgreSQL as a computed column. Zero application code needed for keyword index updates.

### 10. Synchronous ingestion with documented async path

Embedding generation runs synchronously during the index request. This is pragmatic for the assessment scope. In production, this would move to a background task queue (Celery + Redis) to avoid blocking the API during large document ingestion.

## Retrieval Pipeline Design

### Chunking strategy

Documents are split into chunks using word based splitting with configurable size (default: 512 words) and overlap (default: 50 words). Overlap ensures that information at chunk boundaries is not lost. The sample documents are short (~50 words each), so each becomes 1 chunk.

### Embedding

OpenAI `text-embedding-3-small` (1536 dimensions) by default. The provider abstraction supports swapping to HuggingFace `all-MiniLM-L6-v2` (384 dims, runs locally) via environment variable.

### How hallucination is reduced

1. **Grounding prompt**: The LLM system prompt explicitly instructs "answer ONLY based on the provided context" and "cite which passages support each claim."
2. **No answer path**: Low confidence retrievals bypass the LLM entirely.
3. **Temperature zero**: The LLM is called with temperature=0 for deterministic outputs.
4. **Citation enforcement**: The prompt requires [1], [2] style citations.
5. **Context only constraint**: The LLM must say "I don't have enough information" when context is insufficient.

## Known Limitations

1. **Alembic ENUM conflict**: SQLAlchemy auto creates ENUM types when models are imported in `env.py`, conflicting with explicit ENUM creation in the migration. Tables are created via `Base.metadata.create_all()` instead. The migration file is included for reference.
2. **Synchronous ingestion**: The indexing endpoint blocks until chunking and embedding complete.
3. **No reranking step**: A cross encoder reranker between retrieval and generation would improve precision.
4. **Simple chunking**: Word based splitting does not respect sentence or paragraph boundaries.
5. **No caching**: Identical queries hit the full pipeline every time.
6. **Small sample dataset**: With only 3 venues and 3 documents, similarity scores are relatively low. A larger corpus would improve retrieval confidence.
7. **No authentication**: API endpoints have no auth or rate limiting.

## What I Would Build Next

1. **Async ingestion pipeline**: Background job queue (Celery + Redis) for embedding generation
2. **Cross encoder reranking**: Rerank after initial retrieval for better precision
3. **Query expansion**: Rephrase the question multiple ways, merge results for better recall
4. **Evaluation framework**: Automated retrieval quality metrics (precision@k, recall) with a labeled dataset
5. **Redis caching**: Cache frequent queries with TTL to reduce LLM API calls
6. **API authentication**: API key auth and rate limiting
7. **OpenTelemetry tracing**: Distributed tracing across pipeline stages for latency debugging
8. **Multi tenancy**: Organization scoping for documents and queries

## Project Structure

```
telo-venue-assistant/
├── app/
│   ├── api/
│   │   ├── middleware.py          # Request ID middleware
│   │   └── routes/
│   │       ├── documents.py       # Document CRUD + indexing
│   │       ├── queries.py         # RAG query endpoint
│   │       ├── venues.py          # Read only venue listing
│   │       └── health.py          # Health check
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (env vars)
│   │   ├── database.py            # Async SQLAlchemy engine
│   │   ├── dependencies.py        # FastAPI dependency injection
│   │   └── logging.py             # Structured JSON logger
│   ├── models/
│   │   ├── base.py                # Timestamp + soft delete mixins
│   │   ├── venue.py               # Venue model (JSONB amenities, tags, policies)
│   │   ├── document.py            # Document model (ENUM status, soft delete)
│   │   ├── chunk.py               # Chunk model (pgvector + tsvector)
│   │   ├── query.py               # Query log model
│   │   └── query_source.py        # Junction table for citations
│   ├── schemas/                   # Pydantic request/response models
│   ├── services/
│   │   ├── chunking.py            # Text splitting with overlap
│   │   ├── embedding.py           # Abstract base + OpenAI provider
│   │   ├── generation.py          # Abstract base + OpenAI LLM provider
│   │   ├── ingestion.py           # Orchestrates chunk → embed → store
│   │   └── retrieval.py           # Hybrid semantic + keyword search (RRF)
│   └── repositories/              # Database query layer (CRUD)
├── alembic/                       # Database migrations (reference)
├── data/                          # Sample venue + document JSON
├── scripts/seed.py                # Database seeding script
├── tests/                         # pytest test suite
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── requirements.txt
```