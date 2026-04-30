"""Admin API endpoints."""

from .documents import router as documents_router
from .exhibits import router as exhibits_router
from .halls import router as halls_router
from .llm_traces import router as llm_traces_router
from .prompts import router as prompts_router
from .tts_persona import router as tts_persona_router

__all__ = ["documents_router", "exhibits_router", "halls_router", "prompts_router", "llm_traces_router", "tts_persona_router"]
