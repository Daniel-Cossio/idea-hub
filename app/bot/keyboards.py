"""Hito 2: Bot — InlineKeyboardMarkup (Estructurar IA, Prioridad, Estado, Archivar)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_action_keyboard(idea_id: str) -> InlineKeyboardMarkup:
    """Construye el teclado de acciones inline para una idea."""
    buttons = [
        [
            InlineKeyboardButton(
                text="✨ Estructurar con IA",
                callback_data=f"idea:structure:{idea_id}",
            ),
            InlineKeyboardButton(
                text="📋 Copiar Prompt",
                callback_data=f"idea:copy:{idea_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔼 Prioridad Alta",
                callback_data=f"idea:prio:{idea_id}:high",
            ),
            InlineKeyboardButton(
                text="🔽 Prioridad Baja",
                callback_data=f"idea:prio:{idea_id}:low",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ Listo para Agente",
                callback_data=f"idea:ready:{idea_id}",
            ),
            InlineKeyboardButton(
                text="📦 Archivar",
                callback_data=f"idea:archive:{idea_id}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_status_keyboard(idea_id: str) -> InlineKeyboardMarkup:
    """Construye el teclado de cambios de estado."""
    buttons = [
        [
            InlineKeyboardButton(
                text="📥 Inbox",
                callback_data=f"idea:status:{idea_id}:inbox",
            ),
            InlineKeyboardButton(
                text="🔍 Refinando",
                callback_data=f"idea:status:{idea_id}:refining",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤖 Agent-Ready",
                callback_data=f"idea:status:{idea_id}:agent_ready",
            ),
            InlineKeyboardButton(
                text="⚙️ En Desarrollo",
                callback_data=f"idea:status:{idea_id}:in_progress",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ Completada",
                callback_data=f"idea:status:{idea_id}:done",
            ),
            InlineKeyboardButton(
                text="📁 Archivada",
                callback_data=f"idea:status:{idea_id}:archived",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
