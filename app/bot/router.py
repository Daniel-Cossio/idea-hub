"""Hito 2: Bot — Handlers aiogram 3.x (Texto, Reply, Notas de voz, Links, Callbacks)."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from aiogram.filters import Command


def create_bot_router(settings) -> Router:
    """Crea y configura el router del bot Telegram."""
    bot_router = Router()

    @bot_router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Respuesta al comando /start."""
        await message.answer(
            "🚀 **IdeaHub** — Captura ideas desde Telegram.\n\n"
            "Envía un mensaje de texto, nota de voz o enlace.\n"
            "Usa *Reply* a cualquier mensaje para anexar a la idea actual.\n\n"
            "/help para más comandos."
        )

    @bot_router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        """Respuesta al comando /help."""
        await message.answer(
            "**IdeaHub Commands:**\n"
            "/start — Bienvenida\n"
            "/help — Esta ayuda\n"
            "\n**Uso:**\n"
            "• Envía texto, notas de voz o enlaces\n"
            "• Reply a un mensaje para añadir a la idea actual\n"
            "• Usa las tarjetas de acción (inline keyboard)"
        )

    @bot_router.message(F.voice)
    async def handle_voice_message(message: Message, bot: Bot) -> None:
        """Maneja notas de voz."""
        voice = message.voice
        if voice:
            file = await bot.get_file(voice.file_id)
            transcription = (
                f"[voice] Transcripción de nota de voz recibida a las "
                f"{datetime.now(timezone.utc).isoformat()}"
            )
            await message.answer(
                f"🎤 **Voz recibida:**\n\n{transcription}",
                parse_mode="Markdown",
            )

    @bot_router.message(F.link)
    async def handle_link_message(message: Message, bot: Bot) -> None:
        """Maneja mensajes con enlaces."""
        link = message.link
        title = "Enlace"
        await message.answer(
            f"🔗 **Enlace recibido:**\n\n"
            f"**{title}**\n"
            f"{link}"
        )

    @bot_router.message(F.text)
    async def handle_text_message(
        message: Message,
        bot: Bot,
        state: dict = None,
    ) -> None:
        """
        Maneja mensajes de texto.
        Si message.reply_to_message existe, buscar idea_id por message_id en sqlite_index.
        Si existe, anexar al capture_log; si no, crear nueva idea.
        """
        from app.services.idea_service import IdeaService
        from app.models import IdeaCreateRequest, IdeaLogAppendRequest

        settings = type("Settings", (), {
            "data_dir": "./data",
            "sqlite_path": "./data/index.sqlite",
            "telegram_allowed_user_id": "",
        })()

        text = message.text.strip()
        user_id = str(message.from_user.id)

        reply_to = message.reply_to_message
        idea_id = None

        if reply_to and reply_to.from_user and reply_to.from_user.is_bot:
            idea_id = "001"  # Placeholder: extraído del bot message_id
            if idea_id:
                log_req = IdeaLogAppendRequest(
                    entry_text=text,
                    source_type="text",
                    telegram_msg_id=message.message_id,
                )
                service = IdeaService()
                service.append_log_entry(idea_id, log_req)
                await message.answer(
                    f"✅ **Nota anexada a Idea {idea_id}:**\n\n{text}",
                )
                return

        # Crear nueva idea
        req = IdeaCreateRequest(
            raw_input=text,
            source_type="text",
        )
        service = IdeaService()
        idea = service.create_idea(req)
        await message.answer(
            f"📝 **Nueva Idea {idea.id}:**\n\n{text}",
        )

    @bot_router.callback_query(F.data.str().startswith("idea:"))
    async def handle_callback(callback: CallbackQuery, bot: Bot) -> None:
        """Maneja callbacks de botones inline."""
        data = callback.data
        parts = data.split(":")
        action = parts[1]

        if action == "prio":
            priority = parts[3] if len(parts) > 3 else "medium"
            await callback.answer(f"📌 Prioridad {priority}")
            await callback.message.answer(
                f"Prioridad de Idea {parts[2]} actualizada a **{priority}**",
                parse_mode="Markdown",
            )
        elif action == "status":
            status = parts[3] if len(parts) > 3 else "inbox"
            await callback.answer(f"📂 Estado: {status}")
            await callback.message.answer(
                f"Estado de Idea {parts[2]} actualizado a **{status}**",
                parse_mode="Markdown",
            )
        elif action == "structure":
            await callback.answer("✨ Estructurando con IA...")
            await callback.message.answer(
                "✨ **Estructurando Idea...**",
                parse_mode="Markdown",
            )
        elif action == "ready":
            await callback.answer("✅ Idea lista para agente")
            await callback.message.answer(
                f"🤖 Idea {parts[2]} marcada como **Agent-Ready**",
                parse_mode="Markdown",
            )
        elif action == "copy":
            await callback.answer("📋 Prompt copiado")
        elif action == "archive":
            await callback.answer("📦 Idea archivada")
            await callback.message.answer(
                f"📦 Idea {parts[2]} archivada",
                parse_mode="Markdown",
            )

        await callback.answer()

    return bot_router


# Helpers para tests
async def create_test_bot(tmp_path: Path) -> Bot:
    """Crea un Bot de test con token dummy."""
    return Bot(token="123456:ABC-DEF1234gHIJ6KLmNOPQRsvT")
