The system has three layers:

1. **Ingestion pipeline** accepts documents, splits them into overlapping chunks, generates embeddings via OpenAI, and stores everything in PostgreSQL with pgvector.

2. **Storage layer** uses PostgreSQL for both structured data and vector search. Chunks have a pgvector column for semantic search and a tsvector column for keyword search, enabling true hybrid retrieval in a single database.

3. **Query pipeline** embeds the user's question, runs hybrid retrieval (semantic + keyword with Reciprocal Rank Fusion), then sends retrieved passages to an LLM with a grounding prompt that enforces citation and prevents hallucination.

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
git clone https://github.com/YOUR_USERNAME/telo-venue-assistant.git
cd telo-venue-assistant
```

2. Create your environment file:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. Start the services:
```bash
docker-compose up --build
```

4. Run database migrations:
```bash
docker-compose exec app alembic upgrade head
```

5. Seed sample data:
```bash
docker-compose exec app python -m scripts.seed
```

6. The API is now running at `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/api/v1/health`

## How to Run Tests

```bash
# Create test database first (one-time)
docker-compose exec db psql -U telo -c "CREATE DATABASE telo_venue_assistant_test;"

# Run tests
docker-compose exec app pytest tests/ -v
```

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
    "content": "Harbor Loft allows outside catering with prior approval. The venue supports launch events and internal company all-hands. Cancellation with full refund is available up to 14 days before the event.",
    "doc_type": "policy"
  }'

# 2. Index the document (replace DOCUMENT_ID with the id from step 1)
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/index

# 3. Ask a question
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which venues allow outside catering?",
    "top_k": 5
  }'
```

## Design Decisions

### Why pgvector over FAISS or ChromaDB

pgvector keeps vectors in the same PostgreSQL database as structured data. This means hybrid queries (SQL metadata filters + cosine similarity) run in a single query with no cross-system synchronization. For a production system, this eliminates an entire class of consistency bugs and simplifies backup, replication, and monitoring.

### True hybrid search with Reciprocal Rank Fusion

The system runs two parallel searches: semantic (pgvector cosine similarity on embeddings) and keyword (PostgreSQL tsvector/tsquery full-text search). Results are merged using Reciprocal Rank Fusion (RRF), which combines ranked lists without requiring score normalization. Chunks that appear in both result sets get boosted, catching cases where semantic search misses an exact keyword match or keyword search misses a semantically similar passage.

### Provider abstraction (Strategy Pattern)

Both the embedding service and LLM generation service use an abstract base class with concrete implementations for OpenAI and an alternative (HuggingFace for embeddings, Anthropic Claude for generation). Swapping providers is a single environment variable change.

### Denormalized metadata on chunks

Each chunk stores denormalized metadata (venue_id, city, doc_type, venue_name) copied from its parent document. This trades a small amount of write-time duplication for significant read-time speed during retrieval.

### Confidence tiers and the no-answer path

If the best matching chunk has similarity below 0.5, the system returns "I don't have enough information" without calling the LLM. This prevents hallucination from weak context and saves unnecessary LLM API costs.

### Soft delete for documents

Documents are soft-deleted (a deleted_at timestamp is set) rather than hard-deleted. This is standard practice for production systems where accidental deletions happen and audit trails matter.

### Query logging with junction table

Every query is logged with its answer, sources, confidence, and timing metrics. The sources are stored in a proper query_sources junction table (not a JSONB blob) so that analytics queries are possible.

## Retrieval Design

### Chunking strategy

Documents are split into chunks using word-based splitting with configurable size (default: 512 words) and overlap (default: 50 words). Overlap ensures that information at chunk boundaries is not lost.

### How hallucination is reduced

1. **Grounding prompt**: The LLM system prompt explicitly instructs "answer ONLY based on the provided context" and "cite which passages support each claim."
2. **No-answer path**: Low-confidence retrievals bypass the LLM entirely.
3. **Temperature zero**: The LLM is called with temperature=0 for deterministic outputs.
4. **Citation enforcement**: The prompt requires [1], [2] style citations.
5. **Context-only constraint**: The LLM must say "I don't have enough information" when context is insufficient.

## Known Limitations

1. **Ingestion is synchronous**: The indexing endpoint blocks until chunking and embedding complete. In production, this should move to a background task queue (Celery + Redis).
2. **No reranking step**: A cross-encoder reranker between retrieval and generation would improve precision.
3. **Simple chunking**: Word-based splitting does not respect sentence or paragraph boundaries.
4. **No caching**: Identical queries hit the full pipeline every time.

## What I Would Build Next

1. Background job queue (Celery + Redis) for async embedding generation
2. Cross-encoder reranking after initial retrieval
3. Query expansion (rephrase the question multiple ways, merge results)
4. Automated evaluation harness with a labeled dataset
5. API key authentication and rate limiting
6. OpenTelemetry tracing for latency debugging