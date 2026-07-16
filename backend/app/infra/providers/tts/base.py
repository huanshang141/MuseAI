from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


class InvalidWAVAudioError(ValueError):
    """Raised when a provider/cache returns bytes that are not a playable WAV."""


def is_valid_wav(audio: bytes | bytearray | memoryview) -> bool:
    """Validate the RIFF/WAVE container and its required ``fmt``/``data`` chunks."""
    try:
        payload = bytes(audio)
    except (TypeError, ValueError):
        return False
    if len(payload) < 44 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        return False

    riff_end = int.from_bytes(payload[4:8], "little") + 8
    if riff_end < 44 or riff_end > len(payload):
        return False

    found_fmt = False
    found_audio = False
    offset = 12
    while offset + 8 <= riff_end:
        chunk_id = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > riff_end:
            return False
        if chunk_id == b"fmt " and chunk_size >= 16:
            found_fmt = True
        elif chunk_id == b"data" and chunk_size > 0:
            found_audio = True
        offset = chunk_end + (chunk_size % 2)

    return found_fmt and found_audio


def require_valid_wav(audio: bytes | bytearray | memoryview) -> bytes:
    """Return immutable WAV bytes or fail before invalid audio is cached/returned."""
    if not is_valid_wav(audio):
        raise InvalidWAVAudioError("TTS provider returned invalid RIFF/WAVE audio")
    return bytes(audio)


@dataclass
class TTSConfig:
    voice: str
    style: str | None = None


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize_stream(
        self, text: str, config: TTSConfig
    ) -> AsyncGenerator[str, None]:
        """Yield base64-encoded PCM16 audio chunks (24kHz mono)."""
        ...

    @abstractmethod
    async def synthesize(self, text: str, config: TTSConfig) -> bytes:
        """Return complete WAV audio bytes (non-streaming)."""
        ...

    async def close(self) -> None:  # noqa: B027
        pass
