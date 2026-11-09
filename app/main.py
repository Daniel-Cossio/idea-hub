"""Hito 1: Core Foundation — Aplicación FastAPI principal con arranque del Bot Telegram."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from app.config import Settings
from app.services.idea_service import IdeaService
from app.services.ai_service import AIService
from app.api.routes import router as api_router


def _get_settings() -> Settings:
    return Settings()


def _get_idea_service(settings: Settings) -> IdeaService:
    return IdeaService(
        data_dir=settings.data_dir,
        sqlite_path=settings.sqlite_path,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan: inicializa servicios y arranca el bot (si está configurado)."""
    settings = app.state.settings
    service = app.state.idea_service = _get_idea_service(settings)
    app.state.structuring_service = AIService(settings)

    # Rebuild index on startup (< 50 ms)
    service.index.rebuild_index_from_vault(service.vault_dir)

    # Arrancar bot polling en el mismo bucle asyncio (aiogram 3.x)
    bot = None
    bot_task = None
    if settings.telegram_bot_token and not settings.disable_bot_polling:
        from aiogram import Bot, Dispatcher
        from app.bot.router import create_bot_router

        bot = Bot(token=settings.telegram_bot_token)
        dp = Dispatcher()
        dp.include_router(create_bot_router(settings))

        async def start_bot() -> None:
            await dp.start_polling(bot, handle_signals=False)

        bot_task = asyncio.create_task(start_bot())

    yield

    # Cleanup
    if bot_task:
        bot_task.cancel()
    if bot:
        await bot.session.close()
    service.index.close()


app = FastAPI(title="IdeaHub", version="0.1.0", lifespan=lifespan)
app.state.settings = _get_settings()
app.state.idea_service = _get_idea_service(app.state.settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API router before mounting static files (to avoid 404 on /api/*)
app.include_router(api_router)


@app.get("/api/health")
async def healthcheck() -> dict:
    """Healthcheck y conteo en SQLite."""
    service = app.state.idea_service
    count = len(service.index.list_ideas())
    return {"status": "ok", "ideas_count": count}


# Mount static web files if they exist
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
