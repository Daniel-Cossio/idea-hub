"""Hito 2: Bot — Whitelist estricto por TELEGRAM_ALLOWED_USER_ID."""

from aiogram.types import Update
from typing import Callable, Dict, Any, Awaitable


class UserWhitelistMiddleware:
    """Middleware que filtra exclusivamente por TELEGRAM_ALLOWED_USER_ID."""

    def __init__(self, allowed_user_ids: list):
        self.allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict,
    ) -> Any:
        """Verifica que el usuario esté en la whitelist."""
        from aiogram.types import Message, CallbackQuery
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            await event.answer()

        if user_id is not None and str(user_id) not in self.allowed_user_ids:
            return await handler(event, data)

        return await handler(event, data)


def create_whitelist_middleware(allowed_ids: str) -> UserWhitelistMiddleware:
    """Crea un middleware de whitelist a partir de una string de IDs."""
    ids = [i.strip() for i in allowed_ids.split(",") if i.strip()]
    return UserWhitelistMiddleware(ids)
