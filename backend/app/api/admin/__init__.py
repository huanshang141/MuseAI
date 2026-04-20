"""Admin API endpoints."""

from .documents import router as documents_router
from .exhibits import router as exhibits_router
from .halls import router as halls_router
from .prompts import router as prompts_router

__all__ = ["documents_router", "exhibits_router", "halls_router", "prompts_router"]
