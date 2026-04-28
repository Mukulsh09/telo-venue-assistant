"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create custom ENUM types
    document_status = postgresql.ENUM(
        "pending", "indexing", "indexed", "failed",
        name="document_status", create_type=True,
    )
    document_type = postgresql.ENUM(
        "faq", "policy", "operational_note", "booking_detail", "general",
        name="document_type", create_type=True,
    )
    document_status.create(op.get_bind(), checkfirst=True)
    document_type.create(op.get_bind(), checkfirst=True)

    # --- venues ---
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("neighborhood", sa.String(100), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("price_per_head_usd", sa.Numeric(10, 2), nullable=True),
        sa.Column("venue_type", sa.String(50), nullable=True),
        sa.Column("amenities", postgresql.JSONB, server_default="[]"),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("policies", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_venues_city", "venues", ["city"])
    op.create_index("ix_venues_amenities", "venues", ["amenities"], postgresql_using="gin")
    op.create_index("ix_venues_tags", "venues", ["tags"], postgresql_using="gin")

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("venues.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("doc_type", document_type, nullable=False, server_default="general"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", document_status, nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_venue_id", "documents", ["venue_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])
    op.create_index(
        "ix_documents_not_deleted", "documents", ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- chunks ---
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR,
            sa.Computed("to_tsvector('english', content)", persisted=True),
        ),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index(
        "ix_chunks_document_chunk", "chunks",
        ["document_id", "chunk_index"], unique=True,
    )
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_chunks_metadata", "chunks", ["metadata"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding_hnsw", "chunks", ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # --- queries ---
    op.create_table(
        "queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="none"),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("metadata_filters", postgresql.JSONB, nullable=True),
        sa.Column("retrieval_time_ms", sa.Integer, nullable=True),
        sa.Column("generation_time_ms", sa.Integer, nullable=True),
        sa.Column("total_time_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- query_sources ---
    op.create_table(
        "query_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_title", sa.String(500), nullable=True),
        sa.Column("venue_name", sa.String(255), nullable=True),
        sa.Column("excerpt", sa.Text, nullable=True),
        sa.Column("similarity_score", sa.Float, nullable=True),
        sa.Column("keyword_score", sa.Float, nullable=True),
        sa.Column("combined_score", sa.Float, nullable=True),
        sa.Column("rank", sa.Integer, nullable=False),
    )
    op.create_index("ix_query_sources_query_id", "query_sources", ["query_id"])
    op.create_index("ix_query_sources_chunk_id", "query_sources", ["chunk_id"])


def downgrade() -> None:
    op.drop_table("query_sources")
    op.drop_table("queries")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("venues")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS document_type")
    op.execute("DROP EXTENSION IF EXISTS vector")