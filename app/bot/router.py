"""Hito 2: Bot — Handlers aiogram 3.x (Texto, Reply, Notas de voz, Links, Callbacks)."""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.services.idea_service import IdeaService
from app.services.ai_service import AIService
from app.bot.keyboards import build_action_keyboard
from app.models import IdeaCreateRequest, IdeaLogAppendRequest, IdeaStatus, IdeaPriority


def create_bot_router(settings=None) -> Router:
    """Crea y configura el router del bot Telegram."""
    if settings is None:
        from app.config import Settings
        settings = Settings()

    bot_router = Router()
    idea_service = IdeaService(data_dir=settings.data_dir, sqlite_path=settings.sqlite_path)
    ai_service = AIService(settings)

    @bot_router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Respuesta al comando /start."""
        await message.answer(
            "🚀 **IdeaHub** — Captura ideas desde Telegram.\n\n"
            "Envía un mensaje de texto, nota de voz o enlace.\n"
            "Usa *Reply* a cualquier mensaje para anexar a la idea actual.\n\n"
            "/help para más comandos.",
            parse_mode="Markdown",
        )

    @bot_router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        """Respuesta al comando /help."""
        await message.answer(
            "**IdeaHub Commands:**\n"
            "/start — Bienvenida\n"
            "/help — Esta ayuda\n\n"
            "**Uso:**\n"
            "• Envía texto, notas de voz o enlaces\n"
            "• Reply a un mensaje para añadir a la idea actual\n"
            "• Usa las tarjetas de acción (inline keyboard)",
            parse_mode="Markdown",
        )

    @bot_router.message(F.voice)
    async def handle_voice_message(message: Message, bot: Bot) -> None:
        """Maneja notas de voz transcribiéndolas con Groq Whisper."""
        voice = message.voice
        if not voice:
            return

        status_msg = await message.answer("🎙️ _Transcribiendo nota de voz con Groq Whisper..._", parse_mode="Markdown")

        transcription = ""
        try:
            file = await bot.get_file(voice.file_id)
            tmp_path = Path(tempfile.gettempdir()) / f"voice_{voice.file_id}.ogg"
            await bot.download_file(file.file_path, destination=tmp_path)

            transcription = await ai_service.transcribe_voice(str(tmp_path))
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            await status_msg.edit_text(f"❌ Error al procesar audio: {e}")
            return

        if not transcription or transcription.startswith("[Error"):
            await status_msg.edit_text(f"⚠️ {transcription or 'No se pudo transcribir el audio'}")
            return

        # Verificar si es reply a un mensaje de una idea previa
        idea_id = None
        if message.reply_to_message:
            idea_id = idea_service.index.get_idea_id_by_message(message.reply_to_message.message_id)

        if idea_id:
            log_req = IdeaLogAppendRequest(
                entry_text=transcription,
                source_type="voice",
                telegram_msg_id=message.message_id,
            )
            idea_service.append_log_entry(idea_id, log_req)
            idea_service.index.save_message_mapping(message.message_id, idea_id, status_msg.message_id)
            await status_msg.edit_text(
                f"🎙️ **Nota de voz anexada a Idea {idea_id}:**\n\n> {transcription}",
                parse_mode="Markdown",
            )
        else:
            create_req = IdeaCreateRequest(
                raw_input=transcription,
                source_type="voice",
                telegram_msg_id=message.message_id,
            )
            idea = idea_service.create_idea(create_req)
            idea_service.index.save_message_mapping(message.message_id, idea.id, status_msg.message_id)
            await status_msg.edit_text(
                f"💡 **Nueva Idea {idea.id} (Voz):**\n\n> {transcription}",
                reply_markup=build_action_keyboard(idea.id),
                parse_mode="Markdown",
            )

    @bot_router.message(F.text)
    async def handle_text_message(message: Message, bot: Bot) -> None:
        """Maneja mensajes de texto o enlaces."""
        text = message.text.strip()
        if not text:
            return

        reply_to = message.reply_to_message
        idea_id = None
        if reply_to:
            idea_id = idea_service.index.get_idea_id_by_message(reply_to.message_id)

        if idea_id:
            log_req = IdeaLogAppendRequest(
                entry_text=text,
                source_type="text",
                telegram_msg_id=message.message_id,
            )
            idea_service.append_log_entry(idea_id, log_req)
            reply = await message.answer(
                f"✅ **Nota anexada a Idea {idea_id}:**\n\n{text}",
                parse_mode="Markdown",
            )
            idea_service.index.save_message_mapping(message.message_id, idea_id, reply.message_id)
        else:
            create_req = IdeaCreateRequest(
                raw_input=text,
                source_type="text",
                telegram_msg_id=message.message_id,
            )
            idea = idea_service.create_idea(create_req)
            reply = await message.answer(
                f"📝 **Nueva Idea {idea.id}:**\n\n{text}",
                reply_markup=build_action_keyboard(idea.id),
                parse_mode="Markdown",
            )
            idea_service.index.save_message_mapping(message.message_id, idea.id, reply.message_id)

    @bot_router.callback_query(F.data.str().startswith("idea:"))
    async def handle_callback(callback: CallbackQuery, bot: Bot) -> None:
        """Maneja callbacks de botones inline."""
        data = callback.data
        parts = data.split(":")
        action = parts[1]
        idea_id = parts[2] if len(parts) > 2 else ""

        if action == "prio":
            prio_val = parts[3] if len(parts) > 3 else "medium"
            try:
                prio_enum = IdeaPriority(prio_val)
                idea_service.set_priority(idea_id, prio_enum)
                await callback.answer(f"📌 Prioridad {prio_val}")
                await callback.message.answer(
                    f"Prioridad de Idea **{idea_id}** actualizada a **{prio_val}**",
                    parse_mode="Markdown",
                )
            except Exception as e:
                await callback.answer(f"Error: {e}")

        elif action == "status":
            status_val = parts[3] if len(parts) > 3 else "inbox"
            try:
                status_enum = IdeaStatus(status_val)
                idea_service.set_status(idea_id, status_enum)
                await callback.answer(f"📂 Estado {status_val}")
                await callback.message.answer(
                    f"Estado de Idea **{idea_id}** actualizado a **{status_val}**",
                    parse_mode="Markdown",
                )
            except Exception as e:
                await callback.answer(f"Error: {e}")

        elif action == "structure":
            await callback.answer("✨ Estructurando con IA...")
            status_msg = await callback.message.answer(
                f"⏳ _Estructurando especificación de Idea **{idea_id}** con Llama 3.3..._",
                parse_mode="Markdown",
            )
            try:
                idea = idea_service.get_idea(idea_id)
                if idea:
                    structured = await ai_service.structure_with_llm(idea.spec_body or idea.title)
                    idea_service.update_idea(idea_id, IdeaCreateRequest(raw_input=structured))
                    idea_service.set_status(idea_id, IdeaStatus.AGENT_READY)
                    await status_msg.edit_text(
                        f"✨ **Idea {idea_id} estructurada con éxito (`agent_ready`):**\n\n{structured[:300]}...",
                        parse_mode="Markdown",
                    )
            except Exception as e:
                await status_msg.edit_text(f"❌ Error estructurando: {e}")

        elif action == "ready":
            idea_service.set_status(idea_id, IdeaStatus.AGENT_READY)
            await callback.answer("✅ Idea lista para agente")
            await callback.message.answer(
                f"🤖 Idea **{idea_id}** marcada como **Agent-Ready**",
                parse_mode="Markdown",
            )

        elif action == "copy":
            await callback.answer(f"idea-cli init {idea_id}", show_alert=True)

        elif action == "archive":
            idea_service.set_status(idea_id, IdeaStatus.ARCHIVED)
            await callback.answer("📦 Idea archivada")
            await callback.message.answer(
                f"📦 Idea **{idea_id}** archivada",
                parse_mode="Markdown",
            )

        await callback.answer()

    return bot_router


# Router por defecto para compatibilidad
bot_router = create_bot_router(None)


# Helpers para tests
async def create_test_bot(tmp_path: Path) -> Bot:
    """Crea un Bot de test con token dummy."""
    return Bot(token="123456:ABC-DEF1234gHIJ6KLmNOPQRsvT")
