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
        raise HTTPException(
            status_code=503,
            detail="TTS service not available. Check TTS_ENABLED and TTS_API_KEY in server config.",
        )

    config = TTSConfig(voice=body.voice, style=body.style)
    try:
        audio_bytes = await tts_service.provider.synthesize(body.text, config)
    except Exception:
        raise HTTPException(status_code=502, detail="TTS synthesis failed") from None

    return SynthesizeResponse(
        audio=base64.b64encode(audio_bytes).decode("ascii"),
        format="wav",
    )
