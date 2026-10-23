"""Unit and integration tests for Conversational Intent Filter and Similarity Threshold Cutoff."""

import json
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.main import app
from app.models.orm import Chunk, Document
from app.security.rate_limiter import rate_limiter
from app.services.hybrid_search import SearchResult, _dense_search
from app.services.intent import is_conversational_query, is_no_context_answer


@pytest.fixture
def anyio_backend():
    rate_limiter.reset()
    return "asyncio"


def test_is_conversational_query_greetings():
    assert is_conversational_query("How are you today?") is True
    assert is_conversational_query("hello") is True
    assert is_conversational_query("Hi there") is True
    assert is_conversational_query("good morning") is True
    assert is_conversational_query("hey!") is True
    assert is_conversational_query("how is it going?") is True
    assert is_conversational_query("How's the weather?") is True
    assert is_conversational_query("what is the weather today?") is True


def test_is_conversational_query_courtesy_and_identity():
    assert is_conversational_query("thank you so much") is True
    assert is_conversational_query("thanks!") is True
    assert is_conversational_query("who are you?") is True
    assert is_conversational_query("what can you do?") is True
    assert is_conversational_query("help me") is True


def test_is_conversational_query_document_directives():
    assert is_conversational_query("what is in my cv?") is False
    assert is_conversational_query("summarize my resume document") is False
    assert is_conversational_query("find sections discussing machine learning") is False
    assert is_conversational_query("tell me about the candidate's experience") is False


def test_is_conversational_query_factual_questions():
    assert is_conversational_query("What is the capital of Peru?") is False
    assert is_conversational_query("Explain quantum computing in detail") is False


@pytest.mark.anyio
async def test_dense_search_min_similarity_filter():
    """Dense search should exclude chunks whose cosine similarity falls below min_similarity."""
    unique_session = f"test-intent-{uuid.uuid4().hex}"
    await init_db()
    async with async_session_factory() as db_session:
        doc = Document(title="CV.pdf", source="cv.pdf", session_id=unique_session)
        db_session.add(doc)
        await db_session.flush()

        # Create two chunks: one relevant (sim ~ 1.0), one irrelevant (sim ~ 0.0)
        chunk_high = Chunk(
            document_id=doc.id,
            chunk_index=0,
            content="Senior Software Engineer with 10 years experience in Python.",
        )
        # Unit vector along axis 0
        chunk_high.set_embedding([1.0, 0.0, 0.0])

        chunk_low = Chunk(
            document_id=doc.id,
            chunk_index=1,
            content="Unrelated text about cooking recipes and culinary skills.",
        )
        # Unit vector along axis 1 (orthogonal -> cosine similarity = 0.0)
        chunk_low.set_embedding([0.0, 1.0, 0.0])

        db_session.add_all([chunk_high, chunk_low])
        await db_session.commit()

        # Query vector is along axis 0:
        # chunk_high similarity = 1.0 (>= 0.45)
        # chunk_low similarity = 0.0 (< 0.45)
        query_vec = [1.0, 0.0, 0.0]

        results = await _dense_search(
            db_session,
            query_vec=query_vec,
            top_k=5,
            session_id=unique_session,
            min_similarity=0.45,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk_high.id
        assert results[0]["score"] == pytest.approx(1.0)


@pytest.mark.anyio
async def test_conversational_query_skips_retrieval_and_has_empty_sources():
    """POST /api/query/ with 'How are you today?' returns sources == [] and retrieval_ms == 0.0."""
    rate_limiter.reset()
    headers = {"X-Session-ID": "test-session-greeting"}

    with patch.object(settings, "gemini_api_key", ""):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/query/",
                json={"query": "How are you today?", "top_k": 5},
                headers=headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert data["retrieval_ms"] == 0.0
    assert "Blend" in data["answer"] or "help" in data["answer"].lower()


@pytest.mark.anyio
async def test_conversational_stream_emits_empty_sources():
    """POST /api/query/stream with 'Hello!' emits event: sources with sources: [] immediately."""
    rate_limiter.reset()
    headers = {"X-Session-ID": "test-session-greeting-stream"}

    with patch.object(settings, "gemini_api_key", ""):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/query/stream",
                json={"query": "Hello! How are you?", "top_k": 5},
                headers=headers,
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    lines = response.text.strip().split("\n\n")
    events = []
    for block in lines:
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line.replace("event: ", "").strip()
            elif line.startswith("data: "):
                data = json.loads(line.replace("data: ", "").strip())
        events.append((event_type, data))

    # First event MUST be sources with empty sources list and retrieval_ms == 0.0
    assert events[0][0] == "sources"
    assert events[0][1]["sources"] == []
    assert events[0][1]["retrieval_ms"] == 0.0

    # Intermediate events are delta
    deltas = [d["text"] for ev, d in events if ev == "delta"]
    full_text = "".join(deltas)
    assert len(full_text) > 0

    # Final event is done
    assert events[-1][0] == "done"


def test_is_no_context_answer_detection():
    # True positives
    assert is_no_context_answer(
        "The provided documents do not contain information regarding the weather."
    ) is True
    assert is_no_context_answer(
        "The context does not contain enough information to answer."
    ) is True
    assert is_no_context_answer(
        "There is no information regarding weather in the provided documents."
    ) is True
    assert is_no_context_answer(
        "I could not find any relevant information in your uploaded documents."
    ) is True
    assert is_no_context_answer(
        "This topic is not mentioned in the provided documents."
    ) is True
    assert is_no_context_answer(
        "The provided documents do not have any information about salaries."
    ) is True

    # True negatives
    assert is_no_context_answer(
        "According to [Doc: CV.pdf], the candidate has 5 years of Python experience."
    ) is False
    assert is_no_context_answer(
        "The applicant worked at Acme Corp as lead developer."
    ) is False


@pytest.mark.anyio
async def test_query_endpoint_strips_sources_when_model_states_no_info():
    """When the model concludes documents do not contain the answer, sources must be []."""
    rate_limiter.reset()
    headers = {"X-Session-ID": "test-session-no-context"}
    mock_results = [
        SearchResult(
            chunk_id=1,
            document_id=1,
            document_title="CV.pdf",
            content="Resume text here.",
            score=0.88,
        )
    ]

    with (
        patch("app.api.query.hybrid_search", return_value=mock_results),
        patch(
            "app.api.query.generate_answer",
            return_value="The provided documents do not contain information regarding the weather.",
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/query/",
                json={"query": "Tell me about the climate forecast", "top_k": 5},
                headers=headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert "The provided documents do not contain" in data["answer"]


@pytest.mark.anyio
async def test_query_stream_clears_sources_when_model_states_no_info():
    """SSE stream emits updated event: sources with [] and done with clear_sources: True."""
    rate_limiter.reset()
    headers = {"X-Session-ID": "test-session-stream-no-context"}
    mock_results = [
        SearchResult(
            chunk_id=1,
            document_id=1,
            document_title="CV.pdf",
            content="Resume text here.",
            score=0.88,
        )
    ]

    async def mock_stream(*args, **kwargs):
        yield "The provided documents "
        yield "do not contain information regarding the weather."

    with (
        patch("app.api.query.hybrid_search", return_value=mock_results),
        patch("app.api.query.generate_answer_stream", side_effect=mock_stream),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/query/stream",
                json={"query": "Tell me about the climate forecast", "top_k": 5},
                headers=headers,
            )

    assert response.status_code == 200
    lines = response.text.strip().split("\n\n")
    events = []
    for block in lines:
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line.replace("event: ", "").strip()
            elif line.startswith("data: "):
                data = json.loads(line.replace("data: ", "").strip())
        events.append((event_type, data))

    # Should contain two sources events: initial with sources, and cleared with []
    sources_events = [data for ev, data in events if ev == "sources"]
    assert len(sources_events) == 2
    assert len(sources_events[0]["sources"]) == 1
    assert sources_events[1]["sources"] == []

    # Done event should have clear_sources: True
    done_event = next(data for ev, data in events if ev == "done")
    assert done_event["clear_sources"] is True


def test_align_citations_prunes_uncited_and_irrelevant_chunks():
    from app.services.hybrid_search import SearchResult
    from app.services.intent import align_citations_with_answer

    c_header = SearchResult(
        chunk_id=1,
        document_id=1,
        document_title="MartinAbanesCv5",
        content=(
            "--- Page 1 ---\n"
            "Martin I. Abanes\n"
            "Taguig, NCR, Philippines | 09266431076 | miabanes@gmail.com"
        ),
        score=0.016,
    )
    c_skills = SearchResult(
        chunk_id=5,
        document_id=1,
        document_title="MartinAbanesCv5",
        content="CI/CD automated pipelines and application deliveries.",
        score=0.015,
    )
    c_cover = SearchResult(
        chunk_id=14,
        document_id=2,
        document_title="Cover Letter AI Dev",
        content="Dear Hiring Team, I am writing to express my interest...",
        score=0.0155,
    )

    answer = (
        "Based on the provided documents, you live in Taguig, NCR, Philippines "
        "[Doc: MartinAbanesCv5]."
    )
    aligned = align_citations_with_answer(answer, [c_cover, c_skills, c_header])

    # Must contain ONLY c_header (1 citation)
    assert len(aligned) == 1
    assert aligned[0].chunk_id == 1
    assert aligned[0].document_title == "MartinAbanesCv5"


def test_align_citations_handles_multi_chunk_answers():
    from app.services.hybrid_search import SearchResult
    from app.services.intent import align_citations_with_answer

    c1 = SearchResult(
        chunk_id=1,
        document_id=1,
        document_title="Report",
        content="Revenue grew by 25 percent in Q3 due to enterprise software sales.",
        score=0.015,
    )
    c2 = SearchResult(
        chunk_id=2,
        document_id=1,
        document_title="Report",
        content=(
            "Operating costs decreased by 10 percent in Q3 "
            "following automated infrastructure rollout."
        ),
        score=0.014,
    )
    c3 = SearchResult(
        chunk_id=3,
        document_id=2,
        document_title="Unrelated Memo",
        content="Meeting scheduled for Friday morning in cafeteria.",
        score=0.012,
    )

    answer = (
        "In Q3, enterprise software sales grew by 25 percent while "
        "automated infrastructure rollout lowered operating costs [Doc: Report]."
    )
    aligned = align_citations_with_answer(answer, [c1, c2, c3])

    # Both c1 and c2 support the answer; c3 from Unrelated Memo is excluded
    assert len(aligned) == 2
    assert {c.chunk_id for c in aligned} == {1, 2}


