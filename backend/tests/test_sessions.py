"""Unit tests for session-based document isolation, quotas, and expiry pruning."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.session import get_session_id, prune_expired_documents
from app.main import app
from app.models.orm import Chunk, Document
from app.services.hybrid_search import hybrid_search


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.anyio
async def test_get_session_id_header_extraction():
    assert get_session_id("test-session-123") == "test-session-123"
    assert get_session_id("   ") != "   "
    generated = get_session_id(None)
    assert generated.startswith("sess_")


@pytest.mark.anyio
async def test_session_document_isolation():
    session_a = "session_user_alpha"
    session_b = "session_user_beta"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. User A creates a document
        res_a = await client.post(
            "/api/documents/",
            headers={"X-Session-ID": session_a},
            json={
                "title": "Alpha Research",
                "content": "Secret findings for Alpha.",
                "source": "https://alpha.example.com",
            },
        )
        assert res_a.status_code == 201
        doc_a_id = res_a.json()["id"]

        # 2. User B lists documents -> should NOT see User A's document
        res_b_list = await client.get(
            "/api/documents/",
            headers={"X-Session-ID": session_b},
        )
        assert res_b_list.status_code == 200
        items_b = res_b_list.json()["items"]
        assert all(d["id"] != doc_a_id for d in items_b)

        # 3. User B tries to fetch User A's document by ID -> 404
        res_b_get = await client.get(
            f"/api/documents/{doc_a_id}",
            headers={"X-Session-ID": session_b},
        )
        assert res_b_get.status_code == 404

        # 4. User B tries to delete User A's document -> 404
        res_b_del = await client.delete(
            f"/api/documents/{doc_a_id}",
            headers={"X-Session-ID": session_b},
        )
        assert res_b_del.status_code == 404

        # 5. User A can see and delete their own document
        res_a_get = await client.get(
            f"/api/documents/{doc_a_id}",
            headers={"X-Session-ID": session_a},
        )
        assert res_a_get.status_code == 200

        res_a_del = await client.delete(
            f"/api/documents/{doc_a_id}",
            headers={"X-Session-ID": session_a},
        )
        assert res_a_del.status_code == 204


@pytest.mark.anyio
async def test_max_documents_limit():
    session_limit = "session_limit_test"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Patch max_documents_per_session to 2 for quick testing
        with patch.object(settings, "max_documents_per_session", 2):
            # Upload doc 1 -> OK
            r1 = await client.post(
                "/api/documents/",
                headers={"X-Session-ID": session_limit},
                json={"title": "Doc 1", "content": "Content 1"},
            )
            assert r1.status_code == 201

            # Upload doc 2 -> OK
            r2 = await client.post(
                "/api/documents/",
                headers={"X-Session-ID": session_limit},
                json={"title": "Doc 2", "content": "Content 2"},
            )
            assert r2.status_code == 201

            # Upload doc 3 -> Expect 400 Bad Request
            r3 = await client.post(
                "/api/documents/",
                headers={"X-Session-ID": session_limit},
                json={"title": "Doc 3", "content": "Content 3"},
            )
            assert r3.status_code == 400
            assert "Session document limit reached (2/2)" in r3.json()["detail"]

            # Delete doc 1 -> Now count is 1
            doc1_id = r1.json()["id"]
            rdel = await client.delete(
                f"/api/documents/{doc1_id}",
                headers={"X-Session-ID": session_limit},
            )
            assert rdel.status_code == 204

            # Upload doc 3 again -> Now succeeds
            r3_retry = await client.post(
                "/api/documents/",
                headers={"X-Session-ID": session_limit},
                json={"title": "Doc 3", "content": "Content 3"},
            )
            assert r3_retry.status_code == 201

            # Clean up
            await client.delete(
                f"/api/documents/{r2.json()['id']}",
                headers={"X-Session-ID": session_limit},
            )
            await client.delete(
                f"/api/documents/{r3_retry.json()['id']}",
                headers={"X-Session-ID": session_limit},
            )


@pytest.mark.anyio
async def test_prune_expired_documents():
    async with async_session_factory() as db:
        # Create an expired document (8 days old)
        old_time = datetime.now(UTC) - timedelta(days=8)
        doc = Document(
            title="Expired Doc",
            source=None,
            session_id="expired_session",
            created_at=old_time,
            updated_at=old_time,
        )
        db.add(doc)
        await db.flush()

        chunk = Chunk(
            document_id=doc.id,
            chunk_index=0,
            content="Old chunk content",
            embedding_json=None,
            created_at=old_time,
        )
        db.add(chunk)
        await db.commit()

        doc_id = doc.id
        chunk_id = chunk.id

    # Run pruning with 7 day expiry
    async with async_session_factory() as db:
        with patch.object(settings, "session_expiry_days", 7):
            pruned = await prune_expired_documents(db)
            assert pruned >= 1

            # Check that doc and chunk are gone
            check_doc = await db.get(Document, doc_id)
            check_chunk = await db.get(Chunk, chunk_id)
            assert check_doc is None
            assert check_chunk is None


@pytest.mark.anyio
async def test_hybrid_search_session_filter():
    session_x = "session_search_x"
    session_y = "session_search_y"

    async with async_session_factory() as db:
        doc_x = Document(
            title="Project X Architecture",
            source=None,
            session_id=session_x,
        )
        doc_y = Document(
            title="Project Y Architecture",
            source=None,
            session_id=session_y,
        )
        db.add_all([doc_x, doc_y])
        await db.flush()

        chunk_x = Chunk(
            document_id=doc_x.id,
            chunk_index=0,
            content="Project X uses quantum hyper-threading.",
            embedding_json="[0.1, 0.2, 0.3]",
        )
        chunk_y = Chunk(
            document_id=doc_y.id,
            chunk_index=0,
            content="Project Y uses relational databases.",
            embedding_json="[0.4, 0.5, 0.6]",
        )
        db.add_all([chunk_x, chunk_y])
        await db.commit()

        # Hybrid search scoped to session_x with mock query vector
        with patch("app.services.hybrid_search.embed_query", return_value=[0.1, 0.2, 0.3]):
            results_x = await hybrid_search(db, "quantum", session_id=session_x)
            assert all(r.document_id == doc_x.id for r in results_x)

            results_y = await hybrid_search(db, "quantum", session_id=session_y)
            assert all(r.document_id == doc_y.id for r in results_y)

        # Clean up
        await db.delete(chunk_x)
        await db.delete(chunk_y)
        await db.delete(doc_x)
        await db.delete(doc_y)
        await db.commit()
