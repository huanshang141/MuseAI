import base64
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
