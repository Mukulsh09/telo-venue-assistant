import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_document(client: AsyncClient, sample_venue_id: uuid.UUID):
    """Test creating a new document."""
    response = await client.post(
        "/api/v1/documents",
        json={
            "title": "Test FAQ Document",
            "content": "This venue supports events of up to 100 people.",
            "venue_id": str(sample_venue_id),
            "doc_type": "faq",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test FAQ Document"
    assert data["status"] == "pending"
    assert data["doc_type"] == "faq"
    assert data["chunk_count"] == 0


@pytest.mark.asyncio
async def test_create_document_without_venue(client: AsyncClient):
    """Test creating a document not linked to any venue."""
    response = await client.post(
        "/api/v1/documents",
        json={
            "title": "General Policy Guide",
            "content": "All venues must comply with local fire codes.",
            "doc_type": "policy",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["venue_id"] is None
    assert data["doc_type"] == "policy"


@pytest.mark.asyncio
async def test_create_document_validation_error(client: AsyncClient):
    """Test that missing required fields return 422."""
    response = await client.post(
        "/api/v1/documents",
        json={"title": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient):
    """Test listing documents when none exist."""
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_documents_with_pagination(client: AsyncClient):
    """Test pagination on document listing."""
    for i in range(3):
        await client.post(
            "/api/v1/documents",
            json={
                "title": f"Document {i}",
                "content": f"Content for document {i}.",
                "doc_type": "general",
            },
        )

    response = await client.get("/api/v1/documents?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["has_more"] is True

    response = await client.get("/api/v1/documents?limit=2&offset=2")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_get_document_by_id(client: AsyncClient):
    """Test fetching a single document."""
    create_resp = await client.post(
        "/api/v1/documents",
        json={
            "title": "Specific Document",
            "content": "Detailed content here.",
            "doc_type": "faq",
        },
    )
    doc_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient):
    """Test 404 for nonexistent document."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient):
    """Test soft deleting a document."""
    create_resp = await client.post(
        "/api/v1/documents",
        json={
            "title": "To Be Deleted",
            "content": "This document will be soft deleted.",
            "doc_type": "general",
        },
    )
    doc_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_not_found(client: AsyncClient):
    """Test deleting a nonexistent document returns 404."""
    fake_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_bulk_create_documents(client: AsyncClient):
    """Test bulk document ingestion."""
    response = await client.post(
        "/api/v1/documents/bulk",
        json={
            "documents": [
                {"title": "Bulk Doc 1", "content": "Content 1", "doc_type": "faq"},
                {"title": "Bulk Doc 2", "content": "Content 2", "doc_type": "policy"},
                {"title": "Bulk Doc 3", "content": "Content 3", "doc_type": "general"},
            ]
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 3
    assert all(d["status"] == "pending" for d in data)


@pytest.mark.asyncio
async def test_list_documents_filter_by_status(client: AsyncClient):
    """Test filtering documents by status."""
    await client.post(
        "/api/v1/documents",
        json={"title": "Pending Doc", "content": "Content", "doc_type": "faq"},
    )

    response = await client.get("/api/v1/documents?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["status"] == "pending" for item in data["items"])