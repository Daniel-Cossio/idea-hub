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

    # Rebuild index on startup (< 50 ms)
    service.index.rebuild_index_from_vault(service.vault_dir)

    # Arrancar bot polling en el mismo bucle asyncio (aiogram 3.x)
    if settings.telegram_bot_token and not settings.disable_bot_polling:
        from aiogram import Bot, Dispatcher
        from app.bot.router import bot_router

        bot = Bot(token=settings.telegram_bot_token)
        dp = Dispatcher()
        dp.include_router(bot_router)

        async def start_bot() -> None:
            from aiogram.client.session.aiohttp import AiohttpSession
            import aiohttp
            session = AiohttpSession(allocator=aiohttp.TCPConnector())
            bot._session = session
            await dp.start_polling(bot)

        asyncio.create_task(start_bot())

    yield

    # Cleanup
    service.index.close()


app = FastAPI(title="IdeaHub", version="0.1.0", lifespan=lifespan)
app.state.settings = _get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static web files if they exist
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")


@app.get("/api/health")
async def healthcheck() -> dict:
    """Healthcheck y conteo en SQLite."""
    service = app.state.idea_service
    count = len(service.index.list_ideas())
    return {"status": "ok", "ideas_count": count}


@app.on_event("startup")
async def startup() -> None:
    """Inicializa el servicio de ideas."""
    app.state.idea_service = _get_idea_service(app.state.settings)
