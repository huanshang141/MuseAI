import base64
from collections.abc import AsyncGenerator

from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig

_MOCK_PCM16 = b"\x00\x00" * 240  # 10 ms of silence at 24 kHz mono.
_MOCK_FMT = (
    (1).to_bytes(2, "little")
    + (1).to_bytes(2, "little")
    + (24_000).to_bytes(4, "little")
    + (48_000).to_bytes(4, "little")
    + (2).to_bytes(2, "little")
    + (16).to_bytes(2, "little")
)
_MOCK_WAV_BODY = (
    b"fmt "
    + len(_MOCK_FMT).to_bytes(4, "little")
    + _MOCK_FMT
    + b"data"
    + len(_MOCK_PCM16).to_bytes(4, "little")
    + _MOCK_PCM16
)
_MOCK_WAV = (
    b"RIFF"
    + (len(_MOCK_WAV_BODY) + 4).to_bytes(4, "little")
    + b"WAVE"
    + _MOCK_WAV_BODY
)


class MockTTSProvider(BaseTTSProvider):
    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        yield base64.b64encode(_MOCK_PCM16).decode("ascii")

    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        return _MOCK_WAV
