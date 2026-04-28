import os
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

# Use a test database URL (can be overridden via env)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://telo:telo_dev@localhost:5432/telo_venue_assistant_test",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    # Import models to register them
    from app.models.venue import Venue  # noqa: F401
    from app.models.document import Document  # noqa: F401
    from app.models.chunk import Chunk  # noqa: F401
    from app.models.query import Query  # noqa: F401
    from app.models.query_source import QuerySource  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with the test database."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_venue_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a sample venue and return its ID."""
    from sqlalchemy import text

    venue_id = uuid.uuid4()
    await db_session.execute(
        text("""
            INSERT INTO venues (id, name, city, neighborhood, capacity,
                price_per_head_usd, venue_type, amenities, tags, description, policies)
            VALUES (:id, :name, :city, :neighborhood, :capacity,
                :price_per_head_usd, :venue_type, :amenities::jsonb,
                :tags::jsonb, :description, :policies::jsonb)
        """),
        {
            "id": venue_id,
            "name": "Test Venue",
            "city": "Boston",
            "neighborhood": "Seaport",
            "capacity": 100,
            "price_per_head_usd": 85.00,
            "venue_type": "rooftop",
            "amenities": '["AV", "wifi"]',
            "tags": '["startup", "networking"]',
            "description": "A test venue for unit tests.",
            "policies": '{"outside_catering": true, "alcohol_allowed": true}',
        },
    )
    await db_session.commit()
    return venue_id