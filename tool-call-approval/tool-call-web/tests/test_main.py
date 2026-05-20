import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from main import app


def _resp(status: int, body: dict | list) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", "http://backend"))


@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_create_session(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = _resp(200, {"session_id": "abc-123"})

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "abc-123"}
    mock_client.post.assert_called_once_with("http://localhost:8000/sessions", timeout=30.0)


async def test_chat(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = _resp(200, {"status": "processing"})

    with patch("main._client", mock_client):
        resp = await ac.post(
            "/api/sessions/abc-123/chat",
            json={"message": "hello"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "processing"}
    call_args = mock_client.post.call_args
    assert "/sessions/abc-123/chat" in call_args.args[0]
    assert b'"message":"hello"' in call_args.kwargs["content"]


async def test_history(ac):
    mock_client = AsyncMock()
    mock_client.get.return_value = _resp(200, [{"role": "user", "content": "hello"}])

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/abc-123/history")

    assert resp.status_code == 200
    assert resp.json() == [{"role": "user", "content": "hello"}]
    mock_client.get.assert_called_once_with(
        "http://localhost:8000/sessions/abc-123/history", timeout=30.0
    )


async def test_approve(ac):
    mock_client = AsyncMock()
    mock_client.post.return_value = _resp(200, {"status": "ok"})

    with patch("main._client", mock_client):
        resp = await ac.post(
            "/api/sessions/abc-123/approve",
            json={"approved": True},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    call_args = mock_client.post.call_args
    assert "/sessions/abc-123/approve" in call_args.args[0]


async def test_stream(ac):
    async def fake_aiter_text():
        yield 'data: {"type": "message", "content": "hi"}\n\n'
        yield 'data: {"type": "done"}\n\n'

    stream_ctx = MagicMock()
    stream_ctx.aiter_text = fake_aiter_text
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream.return_value = stream_ctx

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/abc-123/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert 'data: {"type": "message"' in resp.text
    assert 'data: {"type": "done"}' in resp.text
    mock_client.stream.assert_called_once_with(
        "GET", "http://localhost:8000/sessions/abc-123/stream"
    )


async def test_session_not_found(ac):
    mock_client = AsyncMock()
    mock_client.get.return_value = _resp(404, {"detail": "Session not found"})

    with patch("main._client", mock_client):
        resp = await ac.get("/api/sessions/bad-id/history")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Session not found"


async def test_backend_unreachable(ac):
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 502
    assert resp.json()["detail"] == "Backend unreachable"


async def test_backend_timeout(ac):
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")

    with patch("main._client", mock_client):
        resp = await ac.post("/api/sessions")

    assert resp.status_code == 504
    assert resp.json()["detail"] == "Backend timeout"
