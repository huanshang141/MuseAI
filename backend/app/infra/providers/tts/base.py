from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


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
