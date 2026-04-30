from collections.abc import AsyncGenerator

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig


class MockTTSProvider(BaseTTSProvider):
    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        yield ""

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        return b""
