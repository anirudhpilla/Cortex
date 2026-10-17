
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, chat, ingestion, search
from app.config import get_settings
from app.database import SessionFactory, engine

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionFactory() as session:
        await session.execute(text("SELECT 1"))

    yield

    await engine.dispose()

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token",
    ],
)

@app.get("/")
async def root() -> dict[str, str]:
    return {"name": settings.app_name}

@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Service not ready",
        ) from None

app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(ingestion.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
