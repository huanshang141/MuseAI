from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.config.settings import get_settings
from app.infra.postgres.database import init_database, close_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    try:
        await init_database(settings.DATABASE_URL)
        yield
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise
    finally:
        await close_database()
        print("Shutting down")


app = FastAPI(title="MuseAI", description="Museum AI Guide System", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
