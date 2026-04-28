import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data


@pytest.mark.asyncio
async def test_request_id_in_response_headers(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    uuid.UUID(response.headers["x-request-id"])


@pytest.mark.asyncio
async def test_create_document_missing_content(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents",
        json={"title": "No Content Doc"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_document_invalid_doc_type(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents",
        json={"title": "Bad Type", "content": "Some content", "doc_type": "invalid_type"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pagination_invalid_params(client: AsyncClient):
    response = await client.get("/api/v1/documents?limit=-1")
    assert response.status_code == 422

    response = await client.get("/api/v1/documents?limit=999")
    assert response.status_code == 422

    response = await client.get("/api/v1/documents?offset=-5")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_document_invalid_uuid(client: AsyncClient):
    response = await client.get("/api/v1/documents/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_index_nonexistent_document(client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await client.post(f"/api/v1/documents/{fake_id}/index")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_query_too_short(client: AsyncClient):
    response = await client.post(
        "/api/v1/query",
        json={"question": "ab"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_invalid_top_k(client: AsyncClient):
    response = await client.post(
        "/api/v1/query",
        json={"question": "Valid question here", "top_k": 0},
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/query",
        json={"question": "Valid question here", "top_k": 50},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_query_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/query/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_venue_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/v1/venues/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_bulk_create_empty_list(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents/bulk",
        json={"documents": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_double_delete(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/documents",
        json={"title": "Double Delete", "content": "Will be deleted twice.", "doc_type": "general"},
    )
    doc_id = create_resp.json()["id"]

    first_delete = await client.delete(f"/api/v1/documents/{doc_id}")
    assert first_delete.status_code == 204

    second_delete = await client.delete(f"/api/v1/documents/{doc_id}")
    assert second_delete.status_code == 404