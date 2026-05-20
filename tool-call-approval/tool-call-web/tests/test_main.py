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
