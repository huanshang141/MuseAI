import base64
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field, StringConstraints

from app.api.deps import TTSSynthesizeRateLimitDep
from app.application.tts_service import DEFAULT_TTS_VOICE
from app.infra.providers.tts.base import (
    InvalidWAVAudioError,
    TTSConfig,
    require_valid_wav,
)

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    # ``voice`` remains a compatibility field; the service currently uses the
    # centrally configured voice even when this value is empty or customized.
    voice: str | None = Field(default=DEFAULT_TTS_VOICE, max_length=64)
    style: str | None = Field(default=None, max_length=500)
    persona: Literal["default", "A", "B", "C", "D"] | None = None


class SynthesizeResponse(BaseModel):
    audio: str  # base64-encoded WAV audio
    format: str = "wav"


def _get_tts_service(request: Request):
    return getattr(request.app.state, "tts_service", None)


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_tts(
    body: SynthesizeRequest,
    request: Request,
    _rate_limit: TTSSynthesizeRateLimitDep,
):
    tts_service = _get_tts_service(request)
    if tts_service is None:
        raise HTTPException(
            status_code=503,
            detail="TTS service not available. Check TTS_ENABLED and TTS_API_KEY in server config.",
        )

    if body.persona:
        config = await tts_service.get_tour_tts_config(body.persona)
        if body.style:
            base_style = config.style or ""
            config.style = (base_style + "\n" + body.style).strip()
    else:
        config = TTSConfig(voice=DEFAULT_TTS_VOICE, style=body.style)
    try:
        audio_bytes = require_valid_wav(
            await tts_service.provider.synthesize(body.text, config)
        )
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    except Exception as exc:
        stage = "wav_validation" if isinstance(exc, InvalidWAVAudioError) else "provider"
        logger.warning(
            "TTS synthesis failed provider={} stage={} error_type={}",
            type(tts_service.provider).__name__,
            stage,
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail="TTS synthesis failed") from None

    return SynthesizeResponse(
        audio=audio_b64,
        format="wav",
    )
