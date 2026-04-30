"""Tests for admin TTS persona API endpoints."""

import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.tts_persona import router
from app.api.deps import get_current_admin_user, get_db_session, get_prompt_cache
from app.domain.entities import Prompt
from app.domain.value_objects import PromptId


def _make_prompt(key="tour_tts_persona_a", voice_desc="五十多岁男性"):
    variables = []
    if voice_desc:
        variables.append({"name": "__voice_description__", "description": voice_desc})
    return Prompt(
        id=PromptId("prompt-1"),
        key=key,
        name="Tour TTS - Archaeologist",
        description=None,
        category="tts",
        content="用沉稳专业的语气讲解",
        variables=variables,
        is_active=True,
        current_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_cache = MagicMock()
    mock_cache.refresh = MagicMock()

    async def override_session():
        yield AsyncMock()

    def override_admin():
        return {"id": "u1", "email": "admin@test.com", "role": "admin"}

    def override_cache():
        return mock_cache

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_current_admin_user] = override_admin
    app.dependency_overrides[get_prompt_cache] = override_cache

    return app, mock_cache


class TestListTtsPersonas:
    def test_returns_personas(self):
        app, mock_cache = _create_app()
        prompts = [_make_prompt("tour_tts_persona_a"), _make_prompt("tour_tts_persona_b")]

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.list_all = AsyncMock(return_value=prompts)
            client = TestClient(app)
            response = client.get("/api/v1/admin/tts/personas")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["personas"][0]["voice_description"] == "五十多岁男性"


class TestGetTtsPersona:
    def test_get_by_letter(self):
        app, _ = _create_app()
        prompt = _make_prompt("tour_tts_persona_a")

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=prompt)
            client = TestClient(app)
            response = client.get("/api/v1/admin/tts/personas/a")

        assert response.status_code == 200
        assert response.json()["key"] == "tour_tts_persona_a"

    def test_invalid_persona_returns_400(self):
        app, _ = _create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/admin/tts/personas/x")
        assert response.status_code == 400

    def test_not_found_returns_404(self):
        app, _ = _create_app()

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=None)
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/admin/tts/personas/a")

        assert response.status_code == 404


class TestUpdateTtsPersona:
    def test_update_content_and_voice_description(self):
        app, mock_cache = _create_app()
        existing = _make_prompt("tour_tts_persona_a", voice_desc="old voice")
        updated = _make_prompt("tour_tts_persona_a", voice_desc="new voice")
        updated.content = "new style"

        with patch("app.api.admin.tts_persona.PostgresPromptRepository") as MockRepo:
            MockRepo.return_value.get_by_key = AsyncMock(return_value=existing)
            MockRepo.return_value.update_with_variables = AsyncMock(return_value=updated)
            client = TestClient(app)
            response = client.put(
                "/api/v1/admin/tts/personas/a",
                json={
                    "content": "new style",
                    "voice_description": "new voice",
                    "change_reason": "test",
                },
            )

        assert response.status_code == 200
        assert response.json()["content"] == "new style"
        mock_cache.refresh.assert_called_once()


class TestVoicePreview:
    def test_503_when_no_api_key(self):
        app, _ = _create_app()

        with patch("app.api.admin.tts_persona.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                TTS_API_KEY="", TTS_BASE_URL="", TTS_VOICE_DESIGN_MODEL=""
            )
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/admin/tts/voice-preview",
                json={"voice_description": "test voice"},
            )

        assert response.status_code == 503

    def test_success(self):
        app, _ = _create_app()
        audio_bytes = b"RIFF" + b"\x00" * 10
        mock_audio = MagicMock()
        mock_audio.data = base64.b64encode(audio_bytes).decode("ascii")
        mock_choice = MagicMock()
        mock_choice.message.audio = mock_audio
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with (
            patch("app.api.admin.tts_persona.get_settings") as mock_settings,
            patch("app.api.admin.tts_persona.AsyncOpenAI") as MockClient,
        ):
            mock_settings.return_value = MagicMock(
                TTS_API_KEY="test-key",
                TTS_BASE_URL="https://api.test.com/v1",
                TTS_VOICE_DESIGN_MODEL="mimo-v2.5-tts-voicedesign",
            )
            MockClient.return_value.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )
            client = TestClient(app)
            response = client.post(
                "/api/v1/admin/tts/voice-preview",
                json={"voice_description": "test voice", "sample_text": "hello"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "wav"
        assert base64.b64decode(data["audio"]) == audio_bytes
