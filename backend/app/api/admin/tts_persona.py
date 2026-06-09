"""Admin API endpoints for TTS persona management."""

import base64

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.api.deps import CurrentAdminUser, PromptCacheDep, SessionDep
from app.application.tts_service import (
    DEFAULT_TTS_VOICE,
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

VALID_PERSONAS = {"a", "b", "c", "d"}
PERSONA_KEY_PREFIX = "tour_tts_persona_"
PERSONA_DEFAULTS = {
    "a": {
        "name": "Tour TTS - 考古研究员",
        "description": "考古研究员语音人设：统一使用冰糖声线，明亮清晰、自然偏快，突出证据与推理边界。",
    },
    "b": {
        "name": "Tour TTS - 研学记录员",
        "description": "研学记录员语音人设：统一使用冰糖声线，明亮清晰、自然偏快，适合边看边记和研学引导。",
    },
    "c": {
        "name": "Tour TTS - 历史追问者",
        "description": "历史追问者语音人设：统一使用冰糖声线，明亮清晰、自然偏快，突出问题意识和历史联系。",
    },
    "d": {
        "name": "Tour TTS - 器物研究员",
        "description": "器物研究员语音人设：统一使用冰糖声线，明亮清晰、自然偏快，适合材料、器形、纹饰和工艺细读。",
    },
}


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


def _normalize_variables(variables: list) -> list[dict[str, str]]:
    """Normalize variables to list of dicts format."""
    if not variables:
        return []
    result = []
    for v in variables:
        if isinstance(v, str):
            result.append({"name": v, "description": ""})
        elif isinstance(v, dict):
            result.append(v)
    return result


def _persona_to_response(prompt: Prompt) -> TtsPersonaResponse:
    normalized = _normalize_variables(prompt.variables)
    persona_code = prompt.key.removeprefix(PERSONA_KEY_PREFIX)
    defaults = PERSONA_DEFAULTS.get(persona_code)
    return TtsPersonaResponse(
        id=prompt.id.value,
        key=prompt.key,
        name=defaults["name"] if defaults else prompt.name,
        description=defaults["description"] if defaults else prompt.description,
        category=prompt.category,
        content=prompt.content,
        voice=extract_voice(normalized),
        voice_description=extract_voice_description(normalized),
        variables=normalized,
        is_active=prompt.is_active,
        current_version=prompt.current_version,
        created_at=prompt.created_at.isoformat(),
        updated_at=prompt.updated_at.isoformat(),
    )


def _validate_persona(persona: str) -> str:
    persona = persona.lower()
    if persona not in VALID_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid persona: {persona}. Must be one of: a, b, c, d",
        )
    return f"{PERSONA_KEY_PREFIX}{persona}"


def _build_tts_variables(base_variables: list | None, voice_description: str | None) -> list[dict[str, str]]:
    new_variables = store_voice_description(base_variables or [], voice_description or "")
    new_variables = [v for v in new_variables if v.get("name") != VOICE_KEY]
    new_variables.append({"name": VOICE_KEY, "description": DEFAULT_TTS_VOICE})
    return new_variables


def _default_tts_content(persona_code: str) -> str:
    names = {"a": "考古研究员", "b": "研学记录员", "c": "历史追问者", "d": "器物研究员"}
    return (
        f"【导览身份】{names[persona_code]}\n"
        "【播报声线】统一使用冰糖声线。声音应清亮、自然、偏年轻女性；"
        "语速稍快但吐字清楚，避免中年男声、拖沓停顿和过度戏剧化。\n"
        "【播报方式】像现场导览员一样直接说明重点，不读出 Markdown 标记，不读出内部处理说明。"
    )


@router.get("/personas", response_model=TtsPersonaListResponse, summary="List TTS personas")
async def list_tts_personas(
    session: SessionDep,
    current_user: CurrentAdminUser,
) -> TtsPersonaListResponse:
    repository = PostgresPromptRepository(session)
    existing_prompts = await repository.list_all(category="tts")
    by_key = {prompt.key: prompt for prompt in existing_prompts}
    created = False
    for persona_code, defaults in PERSONA_DEFAULTS.items():
        key = f"{PERSONA_KEY_PREFIX}{persona_code}"
        if key in by_key:
            continue
        prompt = await repository.create(
            key=key,
            name=defaults["name"],
            category="tts",
            content=_default_tts_content(persona_code),
            description=defaults["description"],
            variables=_build_tts_variables([], None),
        )
        by_key[key] = prompt
        created = True
    if created:
        await session.commit()

    prompts = [by_key[f"{PERSONA_KEY_PREFIX}{code}"] for code in sorted(PERSONA_DEFAULTS)]
    return TtsPersonaListResponse(
        personas=[_persona_to_response(p) for p in prompts if p.is_active],
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
        persona_code = persona.lower()
        defaults = PERSONA_DEFAULTS[persona_code]
        prompt = await repository.create(
            key=key,
            name=defaults["name"],
            category="tts",
            content=request.content,
            description=defaults["description"],
            variables=_build_tts_variables([], request.voice_description),
        )
    else:
        new_variables = _build_tts_variables(existing.variables, request.voice_description)

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

    await prompt_cache.refresh(prompt)
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
