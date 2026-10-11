"""Tests for document creation, listing, retrieval, and deletion."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_document_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create document
        create_res = await client.post(
            "/api/documents/",
            json={"title": "Test Document", "content": "This is test content for retrieval."},
        )
        assert create_res.status_code == 201
        doc_id = create_res.json()["id"]

        # 2. Get document
        get_res = await client.get(f"/api/documents/{doc_id}")
        assert get_res.status_code == 200
        assert get_res.json()["title"] == "Test Document"

        # 3. List documents
        list_res = await client.get("/api/documents/")
        assert list_res.status_code == 200
        assert list_res.json()["total"] >= 1

        # 4. Delete document
        del_res = await client.delete(f"/api/documents/{doc_id}")
        assert del_res.status_code == 204
