"""Admin API endpoints."""

from .exhibits import router as exhibits_router
from .prompts import router as prompts_router

__all__ = ["exhibits_router", "prompts_router"]
