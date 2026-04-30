# TTS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Text-to-Speech to both Q&A and AI Tour chat features using Xiaomi Mimo-V2.5-TTS, with audio delivered as base64 PCM16 chunks in the existing SSE streams.

**Architecture:** Abstract `BaseTTSProvider` (ABC) with factory pattern (mirrors rerank provider). TTS runs server-side after LLM streaming completes, emitting `audio_start → audio_chunk × N → audio_end` events after the existing `done` event. Frontend plays PCM16 via Web Audio API with global toggle + per-message click-to-play fallback.

**Tech Stack:** Python (openai SDK for Xiaomi API), Vue 3 (Web Audio API), existing SSE infrastructure

---

## File Map

### Create
| File | Responsibility |
|------|---------------|
| `backend/app/infra/providers/tts/__init__.py` | Package re-exports |
| `backend/app/infra/providers/tts/base.py` | `BaseTTSProvider` ABC, `TTSConfig` dataclass |
| `backend/app/infra/providers/tts/xiaomi.py` | `XiaomiTTSProvider` — streaming + non-streaming synthesis |
| `backend/app/infra/providers/tts/mock.py` | `MockTTSProvider` for tests |
| `backend/app/infra/providers/tts/factory.py` | `create_tts_provider(settings)` factory |
| `backend/app/application/tts_service.py` | `TTSService` — config resolution for Q&A and tour |
| `backend/app/api/tts.py` | `POST /tts/synthesize` endpoint for click-to-play |
| `frontend/src/composables/useTTSPlayer.js` | Web Audio API PCM16 player composable |
| `backend/tests/unit/test_tts_provider.py` | TTS provider unit tests |
| `backend/tests/unit/test_tts_service.py` | TTS service unit tests |
| `backend/tests/unit/test_tts_api.py` | TTS API contract tests |
| `frontend/src/composables/__tests__/useTTSPlayer.test.js` | Frontend player tests |

### Modify
| File | Change |
|------|--------|
| `backend/app/config/settings.py:68` | Add TTS settings fields after RERANK block |
| `backend/app/application/sse_events.py:35` | Add audio event helpers |
| `backend/app/application/chat_stream_service.py:105,268,391` | Append TTS events after `done` |
| `backend/app/application/tour_chat_service.py:150` | Append TTS events after `done` |
| `backend/app/api/chat.py:108` | Add `tts`/`tts_voice` to `AskRequest` |
| `backend/app/api/tour.py:71` | Add `tts` to `TourChatRequest` |
| `backend/app/main.py:95` | Add TTS provider singleton + TTSService |
| `frontend/src/composables/useChat.js:224` | Handle audio events |
| `frontend/src/composables/useTour.js:175` | Handle audio events |
| `frontend/src/components/chat/ChatMainArea.vue:104` | Handle audio events, add speaker button |
| `frontend/src/components/tour/ExhibitChat.vue` | Handle audio events, add speaker button |
| `frontend/src/components/tour/workspace/TourSettingsPanel.vue:101` | Replace TTS placeholder with real UI |
| `frontend/src/composables/useTourWorkbench.js:20` | Update default voice to preset name |
| `backend/app/main.py:155` | Add TTS provider cleanup in shutdown |

---

## Task 1: TTS Provider Base + Mock

**Files:**
- Create: `backend/app/infra/providers/tts/__init__.py`
- Create: `backend/app/infra/providers/tts/base.py`
- Create: `backend/app/infra/providers/tts/mock.py`
- Test: `backend/tests/unit/test_tts_provider.py`

Reference pattern: `backend/app/infra/providers/rerank/base.py` (lines 25-32)

- [ ] **Step 1: Write failing tests for TTSConfig and BaseTTSProvider**

```python
# backend/tests/unit/test_tts_provider.py
import pytest
from app.infra.providers.tts.base import TTSConfig, BaseTTSProvider
from app.infra.providers.tts.mock import MockTTSProvider


class TestTTSConfig:
    def test_voice_only(self):
        config = TTSConfig(voice="冰糖")
        assert config.voice == "冰糖"
        assert config.style is None

    def test_voice_with_style(self):
        config = TTSConfig(voice="茉莉", style="用温柔的语气")
        assert config.voice == "茉莉"
        assert config.style == "用温柔的语气"


class TestBaseTTSProvider:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseTTSProvider()


class TestMockTTSProvider:
    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_empty_chunk(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        chunks = []
        async for chunk in provider.synthesize_stream("hello", config):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0] == ""

    @pytest.mark.asyncio
    async def test_synthesize_returns_empty_bytes(self):
        provider = MockTTSProvider()
        config = TTSConfig(voice="冰糖")
        result = await provider.synthesize("hello", config)
        assert result == b""

    @pytest.mark.asyncio
    async def test_close(self):
        provider = MockTTSProvider()
        await provider.close()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_tts_provider.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.infra.providers.tts'`

- [ ] **Step 3: Implement TTSConfig and BaseTTSProvider**

```python
# backend/app/infra/providers/tts/base.py
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class TTSConfig:
    voice: str
    style: str | None = None


class BaseTTSProvider(ABC):
    @abstractmethod
    def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        """Yield base64-encoded PCM16 audio chunks (24kHz mono)."""
        ...

    @abstractmethod
    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        """Return complete WAV audio bytes (non-streaming)."""
        ...

    async def close(self) -> None:
        pass
```

- [ ] **Step 4: Implement MockTTSProvider**

```python
# backend/app/infra/providers/tts/mock.py
from collections.abc import AsyncGenerator

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig


class MockTTSProvider(BaseTTSProvider):
    def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        yield ""

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        return b""
```

- [ ] **Step 5: Create package __init__.py**

```python
# backend/app/infra/providers/tts/__init__.py
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider

__all__ = [
    "BaseTTSProvider",
    "TTSConfig",
    "MockTTSProvider",
]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_provider.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/infra/providers/tts/ backend/tests/unit/test_tts_provider.py
git commit -m "feat(tts): add BaseTTSProvider ABC, TTSConfig, and MockTTSProvider"
```

---

## Task 2: Xiaomi TTS Provider

**Files:**
- Create: `backend/app/infra/providers/tts/xiaomi.py`
- Modify: `backend/app/infra/providers/tts/__init__.py`
- Modify: `backend/tests/unit/test_tts_provider.py`

Reference: Xiaomi TTS API doc at `docs/reference/xiaomi_tts.md` — streaming uses `pcm16` format, messages structure requires `assistant` role for text, optional `user` role for style.

- [ ] **Step 1: Write failing tests for XiaomiTTSProvider**

Append to `backend/tests/unit/test_tts_provider.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider


class TestXiaomiTTSProvider:
    def _make_provider(self):
        return XiaomiTTSProvider(
            base_url="https://api.xiaomimimo.com/v1",
            api_key="test-key",
            model="mimo-v2.5-tts",
            timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_synthesize_stream_builds_correct_messages(self):
        provider = self._make_provider()
        config = TTSConfig(voice="冰糖", style="用温柔的语气")

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.audio = {"data": "dGVzdA=="}  # base64 "test"

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = MagicMock(return_value=iter([mock_chunk]))

        with patch.object(provider.client.chat.completions, "create", return_value=mock_stream):
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        assert chunks == ["dGVzdA=="]

    @pytest.mark.asyncio
    async def test_synthesize_stream_no_style(self):
        provider = self._make_provider()
        config = TTSConfig(voice="苏打")

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.audio = {"data": "YQ=="}

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = MagicMock(return_value=iter([mock_chunk]))

        with patch.object(provider.client.chat.completions, "create", return_value=mock_stream) as mock_create:
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        # Verify no user message when style is None
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "你好"

    @pytest.mark.asyncio
    async def test_synthesize_stream_skips_empty_audio(self):
        provider = self._make_provider()
        config = TTSConfig(voice="冰糖")

        mock_chunk_no_audio = MagicMock()
        mock_chunk_no_audio.choices = [MagicMock()]
        mock_chunk_no_audio.choices[0].delta = MagicMock()
        mock_chunk_no_audio.choices[0].delta.audio = None

        mock_chunk_with_audio = MagicMock()
        mock_chunk_with_audio.choices = [MagicMock()]
        mock_chunk_with_audio.choices[0].delta = MagicMock()
        mock_chunk_with_audio.choices[0].delta.audio = {"data": "YQ=="}

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = MagicMock(return_value=iter([mock_chunk_no_audio, mock_chunk_with_audio]))

        with patch.object(provider.client.chat.completions, "create", return_value=mock_stream):
            chunks = []
            async for chunk in provider.synthesize_stream("你好", config):
                chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_close(self):
        provider = self._make_provider()
        with patch.object(provider.client, "close", new_callable=AsyncMock) as mock_close:
            await provider.close()
            mock_close.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tts_provider.py::TestXiaomiTTSProvider -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.infra.providers.tts.xiaomi'`

- [ ] **Step 3: Implement XiaomiTTSProvider**

```python
# backend/app/infra/providers/tts/xiaomi.py
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig


class XiaomiTTSProvider(BaseTTSProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ):
        self.model = model
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        messages = []
        if config.style:
            messages.append({"role": "user", "content": config.style})
        messages.append({"role": "assistant", "content": text})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            audio={"format": "pcm16", "voice": config.voice},
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            audio = getattr(delta, "audio", None)
            if audio and "data" in audio:
                yield audio["data"]

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        import base64

        messages = []
        if config.style:
            messages.append({"role": "user", "content": config.style})
        messages.append({"role": "assistant", "content": text})

        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            audio={"format": "wav", "voice": config.voice},
        )
        audio_data = completion.choices[0].message.audio.data
        return base64.b64decode(audio_data)

    async def close(self) -> None:
        await self.client.close()
```

- [ ] **Step 4: Update __init__.py to export XiaomiTTSProvider**

```python
# backend/app/infra/providers/tts/__init__.py
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider

__all__ = [
    "BaseTTSProvider",
    "TTSConfig",
    "MockTTSProvider",
    "XiaomiTTSProvider",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_provider.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/providers/tts/ backend/tests/unit/test_tts_provider.py
git commit -m "feat(tts): add XiaomiTTSProvider with streaming and non-streaming synthesis"
```

---

## Task 3: TTS Factory

**Files:**
- Create: `backend/app/infra/providers/tts/factory.py`
- Modify: `backend/app/infra/providers/tts/__init__.py`
- Modify: `backend/tests/unit/test_tts_provider.py`

Reference pattern: `backend/app/infra/providers/rerank/factory.py` (lines 10-51)

- [ ] **Step 1: Write failing tests for factory**

Append to `backend/tests/unit/test_tts_provider.py`:

```python
from app.infra.providers.tts.factory import create_tts_provider
from app.config.settings import Settings


class TestCreateTTSProvider:
    def _make_settings(self, **overrides):
        defaults = {
            "TTS_ENABLED": True,
            "TTS_PROVIDER": "xiaomi",
            "TTS_BASE_URL": "https://api.xiaomimimo.com/v1",
            "TTS_API_KEY": "test-key",
            "TTS_MODEL": "mimo-v2.5-tts",
            "TTS_DEFAULT_VOICE": "冰糖",
            "TTS_TIMEOUT": 30.0,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_returns_xiaomi_provider(self):
        settings = self._make_settings()
        provider = create_tts_provider(settings)
        assert isinstance(provider, XiaomiTTSProvider)

    def test_returns_mock_provider(self):
        settings = self._make_settings(TTS_PROVIDER="mock")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)

    def test_returns_none_when_disabled(self):
        settings = self._make_settings(TTS_ENABLED=False)
        provider = create_tts_provider(settings)
        assert provider is None

    def test_returns_none_when_no_api_key(self):
        settings = self._make_settings(TTS_API_KEY="")
        provider = create_tts_provider(settings)
        assert provider is None

    def test_returns_none_for_unknown_provider(self):
        settings = self._make_settings(TTS_PROVIDER="unknown")
        provider = create_tts_provider(settings)
        assert provider is None

    def test_mock_does_not_require_api_key(self):
        settings = self._make_settings(TTS_PROVIDER="mock", TTS_API_KEY="")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tts_provider.py::TestCreateTTSProvider -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.infra.providers.tts.factory'`

- [ ] **Step 3: Implement factory**

```python
# backend/app/infra/providers/tts/factory.py
from loguru import logger

from app.config.settings import Settings
from app.infra.providers.tts.base import BaseTTSProvider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider


def create_tts_provider(settings: Settings) -> BaseTTSProvider | None:
    if not settings.TTS_ENABLED:
        logger.debug("TTS disabled via config, returning None")
        return None

    provider_type = settings.TTS_PROVIDER.lower()

    if provider_type != "mock" and not settings.TTS_API_KEY:
        logger.debug("TTS not configured (no API key), returning None")
        return None

    if provider_type == "xiaomi":
        masked_key = (
            "***" + settings.TTS_API_KEY[-4:]
            if len(settings.TTS_API_KEY) > 4
            else "***"
        )
        logger.info(
            f"Creating Xiaomi TTS provider: model={settings.TTS_MODEL}, "
            f"key={masked_key}"
        )
        return XiaomiTTSProvider(
            base_url=settings.TTS_BASE_URL,
            api_key=settings.TTS_API_KEY,
            model=settings.TTS_MODEL,
            timeout=settings.TTS_TIMEOUT,
        )
    elif provider_type == "mock":
        logger.debug("Creating Mock TTS provider")
        return MockTTSProvider()
    else:
        logger.warning(f"Unknown TTS provider: {provider_type}, returning None")
        return None
```

- [ ] **Step 4: Update __init__.py to export factory**

```python
# backend/app/infra/providers/tts/__init__.py
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig
from app.infra.providers.tts.factory import create_tts_provider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider

__all__ = [
    "BaseTTSProvider",
    "TTSConfig",
    "MockTTSProvider",
    "XiaomiTTSProvider",
    "create_tts_provider",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_provider.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/providers/tts/ backend/tests/unit/test_tts_provider.py
git commit -m "feat(tts): add create_tts_provider factory with xiaomi/mock selection"
```

---

## Task 4: TTS Settings

**Files:**
- Modify: `backend/app/config/settings.py:68` (after RERANK block)

Reference: `backend/app/config/settings.py` lines 57-68 for RERANK settings pattern, lines 132-170 for `validate_production_secrets`.

- [ ] **Step 1: Write failing test for TTS settings**

```python
# backend/tests/unit/test_tts_settings.py
from app.config.settings import Settings


class TestTTSSettings:
    def test_default_values(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="development",
        )
        assert settings.TTS_ENABLED is True
        assert settings.TTS_PROVIDER == "xiaomi"
        assert settings.TTS_BASE_URL == "https://api.xiaomimimo.com/v1"
        assert settings.TTS_API_KEY == ""
        assert settings.TTS_MODEL == "mimo-v2.5-tts"
        assert settings.TTS_DEFAULT_VOICE == "冰糖"
        assert settings.TTS_TIMEOUT == 30.0

    def test_production_requires_tts_api_key_when_provider_set(self):
        try:
            Settings(
                JWT_SECRET="test-secret-that-is-long-enough-32chars",
                LLM_API_KEY="test-key",
                APP_ENV="production",
                TTS_PROVIDER="xiaomi",
                TTS_API_KEY="",
                CORS_ORIGINS="https://example.com",
            )
            assert False, "Should have raised"
        except ValueError as e:
            assert "TTS_API_KEY" in str(e)

    def test_production_allows_empty_tts_key_when_disabled(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="production",
            TTS_ENABLED=False,
            TTS_PROVIDER="xiaomi",
            TTS_API_KEY="",
            CORS_ORIGINS="https://example.com",
        )
        assert settings.TTS_ENABLED is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tts_settings.py -v
```

Expected: FAIL — `ValidationError` (unknown fields `TTS_*`)

- [ ] **Step 3: Add TTS settings fields to Settings class**

Insert after line 68 (after the RERANK block) in `backend/app/config/settings.py`:

```python
    # TTS
    TTS_ENABLED: bool = True
    TTS_PROVIDER: str = "xiaomi"  # xiaomi, mock
    TTS_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "mimo-v2.5-tts"
    TTS_DEFAULT_VOICE: str = "冰糖"
    TTS_TIMEOUT: float = 30.0
```

- [ ] **Step 4: Add TTS validation to production secrets validator**

In `backend/app/config/settings.py`, inside `validate_production_secrets`, after the RERANK check (line 148), add:

```python
            if self.TTS_ENABLED and self.TTS_PROVIDER != "mock" and not self.TTS_API_KEY:
                raise ValueError(
                    "TTS_API_KEY must be set when TTS_PROVIDER is configured in production"
                )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_settings.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/config/settings.py backend/tests/unit/test_tts_settings.py
git commit -m "feat(tts): add TTS configuration settings with production validation"
```

---

## Task 5: TTS Service

**Files:**
- Create: `backend/app/application/tts_service.py`
- Test: `backend/tests/unit/test_tts_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_tts_service.py
import pytest
from unittest.mock import AsyncMock

from app.application.tts_service import TTSService
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider


class TestTTSService:
    def _make_service(self, prompt_gateway=None):
        provider = MockTTSProvider()
        if prompt_gateway is None:
            prompt_gateway = AsyncMock()
            prompt_gateway.get = AsyncMock(return_value=None)
        return TTSService(provider=provider, prompt_gateway=prompt_gateway)

    def test_get_qa_tts_config_default_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config()
        assert config.voice == "冰糖"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    def test_get_qa_tts_config_user_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config(user_voice="苏打")
        assert config.voice == "苏打"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_with_prompt(self):
        gateway = AsyncMock()
        gateway.get = AsyncMock(return_value="用沉稳专业的语气讲解")
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("a")
        assert config.voice == "冰糖"
        assert config.style == "用沉稳专业的语气讲解"
        gateway.get.assert_called_once_with("tour_tts_persona_a")

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_style(self):
        gateway = AsyncMock()
        gateway.get = AsyncMock(return_value=None)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("b")
        assert config.style == "用温和亲切的语气讲解，语速适中"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tts_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.application.tts_service'`

- [ ] **Step 3: Implement TTSService**

```python
# backend/app/application/tts_service.py
from app.application.ports.prompt_gateway import PromptGateway
from app.config.settings import get_settings
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig


class TTSService:
    def __init__(self, provider: BaseTTSProvider, prompt_gateway: PromptGateway):
        self.provider = provider
        self.prompt_gateway = prompt_gateway

    def get_qa_tts_config(self, user_voice: str | None = None) -> TTSConfig:
        settings = get_settings()
        return TTSConfig(
            voice=user_voice or settings.TTS_DEFAULT_VOICE,
            style="用清晰专业的语气讲解，语速适中",
        )

    async def get_tour_tts_config(self, persona: str) -> TTSConfig:
        settings = get_settings()
        prompt_key = f"tour_tts_persona_{persona}"
        style = await self.prompt_gateway.get(prompt_key)
        return TTSConfig(
            voice=settings.TTS_DEFAULT_VOICE,
            style=style or "用温和亲切的语气讲解，语速适中",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_service.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/tts_service.py backend/tests/unit/test_tts_service.py
git commit -m "feat(tts): add TTSService with Q&A and tour config resolution"
```

---

## Task 6: SSE Audio Events

**Files:**
- Modify: `backend/app/application/sse_events.py:35`

Reference: existing `sse_chat_event` at line 26, `sse_tour_event` at line 32.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_sse_audio_events.py
from app.application.sse_events import (
    sse_chat_audio_start,
    sse_chat_audio_chunk,
    sse_chat_audio_end,
    sse_chat_audio_error,
    sse_tour_audio_start,
    sse_tour_audio_chunk,
    sse_tour_audio_end,
    sse_tour_audio_error,
)
import json


class TestChatAudioEvents:
    def test_audio_start(self):
        result = sse_chat_audio_start(voice="冰糖", format="pcm16")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_start"
        assert payload["voice"] == "冰糖"
        assert payload["format"] == "pcm16"

    def test_audio_chunk(self):
        result = sse_chat_audio_chunk(data="dGVzdA==")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_chunk"
        assert payload["data"] == "dGVzdA=="

    def test_audio_end(self):
        result = sse_chat_audio_end()
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_end"

    def test_audio_error(self):
        result = sse_chat_audio_error(code="TTS_ERROR", message="failed")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_error"
        assert payload["code"] == "TTS_ERROR"


class TestTourAudioEvents:
    def test_audio_start(self):
        result = sse_tour_audio_start(voice="冰糖", format="pcm16")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_start"
        assert payload["voice"] == "冰糖"

    def test_audio_chunk(self):
        result = sse_tour_audio_chunk(data="dGVzdA==")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_chunk"
        assert payload["data"] == "dGVzdA=="

    def test_audio_end(self):
        result = sse_tour_audio_end()
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_end"

    def test_audio_error(self):
        result = sse_tour_audio_error(code="TTS_ERROR", message="failed")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_error"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_sse_audio_events.py -v
```

Expected: FAIL — `ImportError: cannot import name 'sse_chat_audio_start'`

- [ ] **Step 3: Add audio event helpers to sse_events.py**

Append to `backend/app/application/sse_events.py` after line 35:

```python
# --- Audio (TTS) event helpers ---


def sse_chat_audio_start(**fields: Any) -> str:
    return sse_chat_event("audio_start", **fields)


def sse_chat_audio_chunk(data: str) -> str:
    return sse_chat_event("audio_chunk", data=data)


def sse_chat_audio_end() -> str:
    return sse_chat_event("audio_end")


def sse_chat_audio_error(code: str, message: str) -> str:
    return sse_chat_event("audio_error", code=code, message=message)


def sse_tour_audio_start(**fields: Any) -> str:
    return sse_tour_event("audio_start", **fields)


def sse_tour_audio_chunk(data: str) -> str:
    return sse_tour_event("audio_chunk", data=data)


def sse_tour_audio_end() -> str:
    return sse_tour_event("audio_end")


def sse_tour_audio_error(code: str, message: str) -> str:
    return sse_tour_event("audio_error", code=code, message=message)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_sse_audio_events.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/sse_events.py backend/tests/unit/test_sse_audio_events.py
git commit -m "feat(tts): add SSE audio event helpers for chat and tour streams"
```

---

## Task 7: Chat Stream TTS Integration

**Files:**
- Modify: `backend/app/application/chat_stream_service.py:105,268,391`
- Modify: `backend/app/api/chat.py:108` (AskRequest model)
- Test: `backend/tests/unit/test_chat_stream_tts.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_chat_stream_tts.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.sse_events import (
    sse_chat_audio_start,
    sse_chat_audio_chunk,
    sse_chat_audio_end,
)
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider


def _parse_events(raw: str) -> list[dict]:
    """Parse SSE stream into list of JSON payloads."""
    events = []
    for line in raw.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestAskRequestTTSFields:
    def test_default_tts_disabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi")
        assert req.tts is False
        assert req.tts_voice is None

    def test_tts_enabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi", tts=True, tts_voice="冰糖")
        assert req.tts is True
        assert req.tts_voice == "冰糖"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_chat_stream_tts.py -v
```

Expected: FAIL — `ValidationError` (unexpected `tts` field)

- [ ] **Step 3: Add TTS fields to AskRequest**

In `backend/app/api/chat.py`, modify `AskRequest` (line 108):

```python
class AskRequest(BaseModel):
    session_id: str
    message: str
    tts: bool = False
    tts_voice: str | None = None
```

- [ ] **Step 4: Run AskRequest tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_chat_stream_tts.py::TestAskRequestTTSFields -v
```

Expected: PASS

- [ ] **Step 5: Write tests for TTS events in chat stream**

Append to `backend/tests/unit/test_chat_stream_tts.py`:

```python
class TestChatStreamTTSEvents:
    """Verify TTS audio events are appended after done event."""

    @pytest.mark.asyncio
    async def test_simple_stream_appends_tts_events(self):
        """ask_question_stream should yield audio_start/chunk/end after done."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = AsyncMock(return_value=iter(["你好"]))

        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="用清晰专业的语气讲解，语速适中")

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                db_session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=tts_provider,
                tts_config=tts_config,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        done_idx = types.index("done")
        assert types[done_idx + 1] == "audio_start"
        assert types[done_idx + 2] == "audio_chunk"
        assert types[done_idx + 3] == "audio_end"

    @pytest.mark.asyncio
    async def test_no_tts_events_when_provider_none(self):
        """When tts_provider is None, no audio events should be emitted."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = AsyncMock(return_value=iter(["你好"]))

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                db_session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=None,
                tts_config=None,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        assert "audio_start" not in types
        assert "audio_chunk" not in types
```

- [ ] **Step 6: Modify chat_stream_service to emit TTS events**

This step requires modifying the function signatures of `ask_question_stream`, `ask_question_stream_with_rag`, and `ask_question_stream_guest` to accept optional `tts_provider` and `tts_config` parameters. After each `done` event yield, add:

```python
        # TTS audio events (after done)
        if tts_provider is not None and tts_config is not None:
            yield sse_chat_audio_start(voice=tts_config.voice, format="pcm16")
            try:
                async for chunk in tts_provider.synthesize_stream(full_content, tts_config):
                    yield sse_chat_audio_chunk(chunk)
                yield sse_chat_audio_end()
            except Exception as e:
                _log.warning(f"TTS synthesis failed: {e}")
                yield sse_chat_audio_error("TTS_ERROR", "语音合成失败")
```

Where `full_content` is the complete LLM response text already assembled in each function.

For `ask_question_stream`: insert after line 105 (after `done` event).
For `ask_question_stream_with_rag`: insert after line 268 (after `done` event).
For `ask_question_stream_guest`: insert after line 391 (after `done` event).

- [ ] **Step 7: Run all tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_chat_stream_tts.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/chat.py backend/app/application/chat_stream_service.py backend/tests/unit/test_chat_stream_tts.py
git commit -m "feat(tts): integrate TTS events into chat SSE streams"
```

---

## Task 8: Tour Stream TTS Integration

**Files:**
- Modify: `backend/app/application/tour_chat_service.py:150`
- Modify: `backend/app/api/tour.py:71` (TourChatRequest model)
- Test: `backend/tests/unit/test_tour_stream_tts.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_tour_stream_tts.py
import json
import pytest
from unittest.mock import AsyncMock

from app.api.tour import TourChatRequest


class TestTourChatRequestTTSField:
    def test_default_tts_disabled(self):
        req = TourChatRequest(message="hi")
        assert req.tts is False

    def test_tts_enabled(self):
        req = TourChatRequest(message="hi", tts=True)
        assert req.tts is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tour_stream_tts.py -v
```

Expected: FAIL — `ValidationError` (unexpected `tts` field)

- [ ] **Step 3: Add TTS field to TourChatRequest**

In `backend/app/api/tour.py`, modify `TourChatRequest` (line 71):

```python
class TourChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    exhibit_id: str | None = None
    style: TourChatStyle | None = None
    tts: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tour_stream_tts.py -v
```

Expected: PASS

- [ ] **Step 5: Modify tour_chat_service to emit TTS events**

In `backend/app/application/tour_chat_service.py`, modify `ask_stream_tour` function signature to accept optional `tts_provider`, `tts_service`, and `persona` parameters. After the `done` event (line 150), add:

```python
    # TTS audio events (after done)
    if tts_provider is not None and tts_service is not None:
        tts_config = await tts_service.get_tour_tts_config(persona)
        yield sse_tour_audio_start(voice=tts_config.voice, format="pcm16")
        try:
            async for chunk in tts_provider.synthesize_stream(full_content, tts_config):
                yield sse_tour_audio_chunk(chunk)
            yield sse_tour_audio_end()
        except Exception as e:
            log.warning(f"TTS synthesis failed: {e}")
            yield sse_tour_audio_error("TTS_ERROR", "语音合成失败")
```

Where `full_content` is the accumulated LLM response text already in scope.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/tour.py backend/app/application/tour_chat_service.py backend/tests/unit/test_tour_stream_tts.py
git commit -m "feat(tts): integrate TTS events into tour SSE stream"
```

---

## Task 9: Standalone TTS Endpoint

**Files:**
- Create: `backend/app/api/tts.py`
- Test: `backend/tests/unit/test_tts_api.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_tts_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.fixture
def mock_tts_service():
    service = AsyncMock()
    service.provider = AsyncMock()
    service.provider.synthesize = AsyncMock(return_value=b"\x00" * 100)
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
    assert data["format"] == "wav"


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/unit/test_tts_api.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TTS endpoint**

```python
# backend/app/api/tts.py
import base64

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.providers.tts.base import TTSConfig

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "冰糖"
    style: str | None = None


class SynthesizeResponse(BaseModel):
    audio: str  # base64-encoded WAV
    format: str = "wav"


def _get_tts_service(request: Request):
    return getattr(request.app.state, "tts_service", None)


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_tts(body: SynthesizeRequest, request: Request):
    tts_service = _get_tts_service(request)
    if tts_service is None:
        raise HTTPException(status_code=503, detail="TTS service not available")

    config = TTSConfig(voice=body.voice, style=body.style)
    try:
        audio_bytes = await tts_service.provider.synthesize(body.text, config)
    except Exception:
        raise HTTPException(status_code=502, detail="TTS synthesis failed")

    return SynthesizeResponse(
        audio=base64.b64encode(audio_bytes).decode("ascii"),
        format="wav",
    )
```

- [ ] **Step 4: Wire up dependency injection**

In `backend/app/main.py`, add the router registration and dependency override. The endpoint will use `request.app.state.tts_service` for dependency injection.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest backend/tests/unit/test_tts_api.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/tts.py backend/tests/unit/test_tts_api.py backend/app/main.py
git commit -m "feat(tts): add standalone POST /tts/synthesize endpoint for click-to-play"
```

---

## Task 10: Singleton Init + API Wiring

**Files:**
- Modify: `backend/app/main.py:95,135-148,155,230-242`

- [ ] **Step 1: Add TTS provider and service to lifespan**

In `backend/app/main.py`, after `rerank_provider = create_rerank_provider(settings)` (line 95), add:

```python
        from app.infra.providers.tts.factory import create_tts_provider

        tts_provider = create_tts_provider(settings)
```

After `prompt_gateway = PromptServiceAdapter(prompt_cache)` (line 104), add:

```python
        tts_service = None
        if tts_provider is not None:
            from app.application.tts_service import TTSService

            tts_service = TTSService(provider=tts_provider, prompt_gateway=prompt_gateway)
```

In the `app.state` assignments block (after line 148), add:

```python
        app.state.tts_provider = tts_provider
        app.state.tts_service = tts_service
```

- [ ] **Step 2: Add TTS provider cleanup in shutdown**

In the `finally` block (after line 160), add:

```python
        if hasattr(app.state, "tts_provider") and app.state.tts_provider:
            await app.state.tts_provider.close()
```

- [ ] **Step 3: Register TTS router**

In the router registration section (around line 242), add:

```python
    from app.api.tts import router as tts_router
    app.include_router(tts_router, prefix="/api/v1")
```

- [ ] **Step 4: Update chat and tour endpoints to pass TTS params**

In `backend/app/api/chat.py`, update `ask_stream_endpoint` to extract `tts_provider` and `tts_service` from `request.app.state`, construct `TTSConfig` if `ask_request.tts` is True, and pass them to the streaming generator.

In `backend/app/api/tour.py`, update `tour_chat_stream` similarly, using `tts_service` for persona-based config.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest backend/tests/unit -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/chat.py backend/app/api/tour.py
git commit -m "feat(tts): wire TTS provider, service, and endpoints into app lifecycle"
```

---

## Task 11: Tour TTS Prompts (Seed Data)

**Files:**
- Create: `backend/scripts/seed_tts_prompts.py`

- [ ] **Step 1: Create seed script**

```python
# backend/scripts/seed_tts_prompts.py
"""Seed TTS persona prompts into the prompt system.

Run: uv run python backend/scripts/seed_tts_prompts.py
"""
import asyncio

from app.config.settings import get_settings
from app.infra.postgres.database import get_session
from app.infra.postgres.adapters.prompt import PostgresPromptRepository
from app.infra.cache.prompt_cache import PromptCache
from app.application.prompt_service import PromptService

TTS_PROMPTS = [
    {
        "key": "tour_tts_persona_a",
        "name": "Tour TTS - Archaeologist",
        "category": "tts",
        "content": "用沉稳专业的语气讲解，语速适中，带有学术气息，像一位资深考古学家在分享发现",
        "variables": [],
    },
    {
        "key": "tour_tts_persona_b",
        "name": "Tour TTS - Villager",
        "category": "tts",
        "content": "用亲切朴实的语气讲述，语速稍慢，带有乡音的温暖感，像一位老村民在回忆往事",
        "variables": [],
    },
    {
        "key": "tour_tts_persona_c",
        "name": "Tour TTS - Teacher",
        "category": "tts",
        "content": "用生动有趣的语气讲解，语速适中，善于用比喻和提问吸引注意力，像一位热情的历史老师",
        "variables": [],
    },
]


async def main():
    settings = get_settings()
    async with get_session() as session:
        repo = PostgresPromptRepository(session)
        cache = PromptCache()
        cache.set_repository(repo)
        service = PromptService(repo, cache)

        for prompt in TTS_PROMPTS:
            existing = await service.get_prompt(prompt["key"])
            if existing:
                print(f"  [skip] {prompt['key']} already exists")
                continue
            await service.create_prompt(
                key=prompt["key"],
                name=prompt["name"],
                category=prompt["category"],
                content=prompt["content"],
                variables=prompt["variables"],
            )
            print(f"  [created] {prompt['key']}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/seed_tts_prompts.py
git commit -m "feat(tts): add seed script for tour TTS persona prompts"
```

---

## Task 12: Frontend TTS Player Composable

**Files:**
- Create: `frontend/src/composables/useTTSPlayer.js`
- Test: `frontend/src/composables/__tests__/useTTSPlayer.test.js`

- [ ] **Step 1: Write failing tests**

```javascript
// frontend/src/composables/__tests__/useTTSPlayer.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTTSPlayer } from '../useTTSPlayer.js'

// Mock AudioContext
const mockCreateBuffer = vi.fn()
const mockCreateBufferSource = vi.fn()
const mockConnect = vi.fn()
const mockStart = vi.fn()
const mockDestination = {}

class MockAudioContext {
  constructor() {
    this.currentTime = 0
    this.destination = mockDestination
  }
  createBuffer(channels, length, sampleRate) {
    return {
      getChannelData: () => new Float32Array(length),
      duration: length / sampleRate,
    }
  }
  createBufferSource() {
    return { buffer: null, connect: mockConnect, start: mockStart }
  }
}

describe('useTTSPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with isPlaying false', () => {
    const { isPlaying } = useTTSPlayer()
    expect(isPlaying.value).toBe(false)
  })

  it('feedChunk schedules audio playback', () => {
    global.AudioContext = MockAudioContext
    const { feedChunk, isPlaying } = useTTSPlayer()

    // Create a simple PCM16 base64 chunk (2 samples)
    const int16 = new Int16Array([16000, -16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    expect(isPlaying.value).toBe(true)
    expect(mockStart).toHaveBeenCalled()
  })

  it('stop resets state', () => {
    global.AudioContext = MockAudioContext
    const { feedChunk, stop, isPlaying } = useTTSPlayer()

    const int16 = new Int16Array([16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    stop()
    expect(isPlaying.value).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/singer/MuseAI/frontend && npx vitest run src/composables/__tests__/useTTSPlayer.test.js
```

Expected: FAIL — module not found

- [ ] **Step 3: Implement useTTSPlayer**

```javascript
// frontend/src/composables/useTTSPlayer.js
import { ref } from 'vue'

export function useTTSPlayer() {
  const isPlaying = ref(false)

  let audioContext = null
  let scheduledEndTime = 0
  let currentSources = []

  function initContext() {
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 24000 })
    }
  }

  function feedChunk(base64Chunk) {
    if (!base64Chunk) return
    initContext()

    // Decode base64 -> Int16 -> Float32
    const raw = atob(base64Chunk)
    const int16 = new Int16Array(raw.length / 2)
    for (let i = 0; i < int16.length; i++) {
      int16[i] = (raw.charCodeAt(i * 2 + 1) << 8) | raw.charCodeAt(i * 2)
    }
    const float32 = Float32Array.from(int16, (v) => v / 32768)

    // Create AudioBuffer and schedule gapless playback
    const buffer = audioContext.createBuffer(1, float32.length, 24000)
    buffer.getChannelData(0).set(float32)
    const source = audioContext.createBufferSource()
    source.buffer = buffer
    source.connect(audioContext.destination)

    const startTime = Math.max(audioContext.currentTime, scheduledEndTime)
    source.start(startTime)
    scheduledEndTime = startTime + buffer.duration

    currentSources.push(source)
    source.onended = () => {
      currentSources = currentSources.filter((s) => s !== source)
      if (currentSources.length === 0) {
        isPlaying.value = false
      }
    }
    isPlaying.value = true
  }

  function stop() {
    for (const source of currentSources) {
      try {
        source.stop()
      } catch {}
    }
    currentSources = []
    isPlaying.value = false
    scheduledEndTime = 0
  }

  return { isPlaying, feedChunk, stop }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/composables/__tests__/useTTSPlayer.test.js
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useTTSPlayer.js frontend/src/composables/__tests__/useTTSPlayer.test.js
git commit -m "feat(tts): add useTTSPlayer composable with Web Audio API PCM16 playback"
```

---

## Task 13: Chat TTS Integration (Frontend)

**Files:**
- Modify: `frontend/src/composables/useChat.js:224`
- Modify: `frontend/src/components/chat/ChatMainArea.vue:95-128`

- [ ] **Step 1: Update useChat.js to pass TTS params and handle audio events**

In `frontend/src/composables/useChat.js`:

1. Add TTS request parameters to `api.chat.askStream` and `api.chat.guestMessage` calls
2. The composable passes through all events (including new audio events) to the caller — no changes needed in the generator itself since it already yields all events.

The key change is in the API client call — pass `tts` and `tts_voice` from localStorage preferences.

- [ ] **Step 2: Update ChatMainArea.vue to handle audio events**

In `frontend/src/components/chat/ChatMainArea.vue`, import `useTTSPlayer` and add audio event handling:

```javascript
import { useTTSPlayer } from '../../composables/useTTSPlayer.js'

const { isPlaying: ttsPlaying, feedChunk, stop: stopTTS } = useTTSPlayer()

// TTS preferences from localStorage
const ttsEnabled = ref(localStorage.getItem('chat_tts_enabled') === 'true')
const ttsVoice = ref(localStorage.getItem('chat_tts_voice') || '冰糖')
```

In the `handleSendMessage` event loop, after the existing `rag_step` handler, add:

```javascript
      } else if (event.type === 'audio_start') {
        stopTTS() // clear any previous playback
      } else if (event.type === 'audio_chunk') {
        if (ttsEnabled.value) {
          feedChunk(event.data)
        }
      } else if (event.type === 'audio_end') {
        // playback finishes naturally via onended
      } else if (event.type === 'audio_error') {
        console.warn('TTS error:', event.message)
      }
```

Add a speaker icon button in the message template for click-to-play via the `/tts/synthesize` endpoint.

- [ ] **Step 3: Add TTS toggle and voice selector to chat UI**

Add a toggle button in the chat header area and a voice selector dropdown. Store preferences in localStorage keys `chat_tts_enabled` and `chat_tts_voice`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useChat.js frontend/src/components/chat/ChatMainArea.vue
git commit -m "feat(tts): add TTS audio playback to chat UI with toggle and voice selector"
```

---

## Task 14: Tour TTS Integration (Frontend)

**Files:**
- Modify: `frontend/src/composables/useTour.js:175`
- Modify: `frontend/src/components/tour/ExhibitChat.vue`
- Modify: `frontend/src/components/tour/workspace/TourSettingsPanel.vue:101-107`
- Modify: `frontend/src/composables/useTourWorkbench.js:20-24`

- [ ] **Step 1: Update DEFAULT_TTS_PREFERENCES in useTourWorkbench.js**

In `frontend/src/composables/useTourWorkbench.js`, update line 20-24:

```javascript
const DEFAULT_TTS_PREFERENCES = {
  voice: '冰糖',
  autoPlay: true,
  enabled: true,
}
```

- [ ] **Step 2: Update useTour.js to handle audio events**

In `frontend/src/composables/useTour.js`, import `useTTSPlayer` and add audio event handling in `sendTourMessage`:

```javascript
import { useTTSPlayer } from './useTTSPlayer.js'

// Inside the composable:
const { isPlaying: ttsPlaying, feedChunk, stop: stopTTS } = useTTSPlayer()
```

In the `for await` loop (after the `error` handler at line 185), add:

```javascript
        } else if (event.event === 'audio_start') {
          stopTTS()
        } else if (event.event === 'audio_chunk') {
          if (ttsPreferences.value.enabled && ttsPreferences.value.autoPlay) {
            feedChunk(event.data)
          }
        } else if (event.event === 'audio_end') {
          // playback finishes naturally
        } else if (event.event === 'audio_error') {
          console.warn('TTS error:', event.data?.message)
        }
```

Pass `tts: ttsPreferences.value.enabled` in the API call to `api.tour.chatStream`.

- [ ] **Step 3: Replace TTS placeholder in TourSettingsPanel.vue**

In `frontend/src/components/tour/workspace/TourSettingsPanel.vue`, replace lines 101-107:

```vue
    <div class="settings-section tts-section">
      <h4 class="settings-heading">语音朗读</h4>
      <label class="settings-toggle">
        <input type="checkbox" v-model="ttsPreferences.enabled" />
        <span>启用语音朗读</span>
      </label>
      <label class="settings-toggle" v-if="ttsPreferences.enabled">
        <input type="checkbox" v-model="ttsPreferences.autoPlay" />
        <span>自动播放</span>
      </label>
      <div class="settings-field" v-if="ttsPreferences.enabled">
        <label class="settings-label">音色</label>
        <select v-model="ttsPreferences.voice" class="settings-select">
          <option value="冰糖">冰糖 (女)</option>
          <option value="茉莉">茉莉 (女)</option>
          <option value="苏打">苏打 (男)</option>
          <option value="白桦">白桦 (男)</option>
          <option value="Mia">Mia (EN/F)</option>
          <option value="Chloe">Chloe (EN/F)</option>
          <option value="Milo">Milo (EN/M)</option>
          <option value="Dean">Dean (EN/M)</option>
        </select>
      </div>
    </div>
```

- [ ] **Step 4: Add speaker button to ExhibitChat.vue**

In `frontend/src/components/tour/ExhibitChat.vue`, add a speaker icon button on each assistant message for click-to-play via `POST /api/v1/tts/synthesize`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useTour.js frontend/src/composables/useTourWorkbench.js frontend/src/components/tour/ExhibitChat.vue frontend/src/components/tour/workspace/TourSettingsPanel.vue
git commit -m "feat(tts): add TTS playback to tour UI with settings panel and speaker button"
```

---

## Task 15: End-to-End Verification

- [ ] **Step 1: Run full backend test suite**

```bash
uv run pytest backend/tests/unit backend/tests/contract -v
```

Expected: all tests PASS

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests PASS

- [ ] **Step 3: Run linters**

```bash
uv run ruff check backend/
cd frontend && npm run lint
```

Expected: no errors

- [ ] **Step 4: Manual smoke test**

1. Start backend: `uv run uvicorn backend.app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open browser, start a chat session
4. Enable TTS toggle, send a message
5. Verify: text streams normally, then audio_start/audio_chunk/audio_end events arrive and audio plays
6. Test click-to-play: disable TTS, send a message, click speaker icon
7. Test tour: start a tour, enable TTS in settings panel, ask a question
8. Verify persona-specific TTS style is applied

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(tts): address e2e verification findings"
```
