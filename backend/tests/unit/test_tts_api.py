import base64

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


async def _async_iter(items):
    for item in items:
        yield item


@pytest.fixture
def mock_tts_service():
    service = AsyncMock()
    service.provider = AsyncMock()
    service.provider.synthesize_stream = MagicMock(
        return_value=_async_iter(["AAAA", "BBBB"])
    )
    return service


@pytest.mark.asyncio
async def test_synthesize_endpoint(mock_tts_service):
    with patch("app.api.tts._get_tts_service", return_value=mock_tts_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": "冰糖"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "audio" in data
    assert data["format"] == "pcm16"
    assert data["audio"] == "AAAABBBB"


@pytest.mark.asyncio
async def test_synthesize_returns_503_when_tts_unavailable():
    with patch("app.api.tts._get_tts_service", return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": "你好", "voice": "冰糖"},
            )
    assert resp.status_code == 503
