"""Admin API endpoints for TTS persona management."""

import base64

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.api.deps import CurrentAdminUser, PromptCacheDep, SessionDep
from app.application.tts_service import (
    VOICE_KEY,
    extract_voice,
    extract_voice_description,
    store_voice_description,
)
from app.config.settings import get_settings
from app.domain.entities import Prompt
from app.domain.exceptions import PromptNotFoundError
from app.infra.postgres.adapters import PostgresPromptRepository

router = APIRouter(prefix="/admin/tts", tags=["admin-tts"])

VALID_PERSONAS = {"a", "b", "c"}
PERSONA_KEY_PREFIX = "tour_tts_persona_"


class TtsPersonaResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    category: str
    content: str
    voice: str | None
    voice_description: str | None
    variables: list[dict[str, str]]
    is_active: bool
    current_version: int
    created_at: str
    updated_at: str


class TtsPersonaListResponse(BaseModel):
    personas: list[TtsPersonaResponse]
    total: int


class UpdateTtsPersonaRequest(BaseModel):
    content: str
    voice: str | None = None
    voice_description: str | None = None
    change_reason: str | None = None


class VoicePreviewRequest(BaseModel):
    voice_description: str
    sample_text: str = "大家好，欢迎来到博物馆，我是今天的讲解员"


class VoicePreviewResponse(BaseModel):
    audio: str  # base64-encoded WAV
    format: str = "wav"


def _persona_to_response(prompt: Prompt) -> TtsPersonaResponse:
    return TtsPersonaResponse(
        id=prompt.id.value,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        voice=extract_voice(prompt.variables),
        voice_description=extract_voice_description(prompt.variables),
        variables=prompt.variables,
        is_active=prompt.is_active,
        current_version=prompt.current_version,
        created_at=prompt.created_at.isoformat(),
        updated_at=prompt.updated_at.isoformat(),
    )


def _validate_persona(persona: str) -> str:
    if persona not in VALID_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid persona: {persona}. Must be one of: a, b, c",
        )
    return f"{PERSONA_KEY_PREFIX}{persona}"


@router.get("/personas", response_model=TtsPersonaListResponse, summary="List TTS personas")
async def list_tts_personas(
    session: SessionDep,
    current_user: CurrentAdminUser,
) -> TtsPersonaListResponse:
    repository = PostgresPromptRepository(session)
    prompts = await repository.list_all(category="tts")
    return TtsPersonaListResponse(
        personas=[_persona_to_response(p) for p in prompts],
        total=len(prompts),
    )


@router.get("/personas/{persona}", response_model=TtsPersonaResponse, summary="Get TTS persona")
async def get_tts_persona(
    session: SessionDep,
    persona: str,
    current_user: CurrentAdminUser,
) -> TtsPersonaResponse:
    key = _validate_persona(persona)
    repository = PostgresPromptRepository(session)
    prompt = await repository.get_by_key(key)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS persona not found: {persona}",
        )
    return _persona_to_response(prompt)


@router.put("/personas/{persona}", response_model=TtsPersonaResponse, summary="Update TTS persona")
async def update_tts_persona(
    session: SessionDep,
    persona: str,
    request: UpdateTtsPersonaRequest,
    current_user: CurrentAdminUser,
    prompt_cache: PromptCacheDep,
) -> TtsPersonaResponse:
    key = _validate_persona(persona)
    repository = PostgresPromptRepository(session)

    existing = await repository.get_by_key(key)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS persona not found: {persona}",
        )

    new_variables = store_voice_description(
        existing.variables, request.voice_description or ""
    )

    if request.voice is not None:
        new_variables = [v for v in new_variables if v.get("name") != VOICE_KEY]
        if request.voice:
            new_variables.append({"name": VOICE_KEY, "description": request.voice})

    try:
        prompt = await repository.update_with_variables(
            key=key,
            content=request.content,
            variables=new_variables,
            changed_by=current_user.get("email"),
            change_reason=request.change_reason,
        )
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS persona not found: {persona}",
        ) from None

    prompt_cache.refresh(prompt)
    return _persona_to_response(prompt)


@router.post("/voice-preview", response_model=VoicePreviewResponse, summary="Preview voice design")
async def voice_preview(
    current_user: CurrentAdminUser,
    request: VoicePreviewRequest,
) -> VoicePreviewResponse:
    settings = get_settings()

    if not settings.TTS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service not configured. Set TTS_API_KEY in server config.",
        )

    client = AsyncOpenAI(
        base_url=settings.TTS_BASE_URL,
        api_key=settings.TTS_API_KEY,
    )

    try:
        completion = await client.chat.completions.create(
            model=settings.TTS_VOICE_DESIGN_MODEL,
            messages=[
                {"role": "user", "content": request.voice_description},
                {"role": "assistant", "content": request.sample_text},
            ],
            audio={"format": "wav"},
        )
        audio_data = completion.choices[0].message.audio.data
        audio_bytes = base64.b64decode(audio_data)
    except Exception as e:
        logger.error(f"Voice design preview failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Voice design synthesis failed",
        ) from None

    return VoicePreviewResponse(
        audio=base64.b64encode(audio_bytes).decode("ascii"),
        format="wav",
    )
