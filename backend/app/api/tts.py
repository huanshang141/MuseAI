from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.providers.tts.base import TTSConfig

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "冰糖"
    style: str | None = None
    persona: str | None = None


class SynthesizeResponse(BaseModel):
    audio: str  # base64-encoded PCM16
    format: str = "pcm16"


def _get_tts_service(request: Request):
    return getattr(request.app.state, "tts_service", None)


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_tts(body: SynthesizeRequest, request: Request):
    tts_service = _get_tts_service(request)
    if tts_service is None:
        raise HTTPException(
            status_code=503,
            detail="TTS service not available. Check TTS_ENABLED and TTS_API_KEY in server config.",
        )

    if body.persona:
        config = await tts_service.get_tour_tts_config(body.persona)
    else:
        config = TTSConfig(voice=body.voice, style=body.style)
    try:
        # Use synthesize_stream to get PCM16 chunks, collect all into one buffer
        chunks = []
        async for chunk in tts_service.provider.synthesize_stream(body.text, config):
            chunks.append(chunk)
        audio_b64 = "".join(chunks)
    except Exception:
        raise HTTPException(status_code=502, detail="TTS synthesis failed") from None

    return SynthesizeResponse(
        audio=audio_b64,
        format="pcm16",
    )
