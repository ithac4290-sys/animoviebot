from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from bot.database import db


class UserRegisterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: User = data.get("event_from_user")
        if event_user:
            await db.add_or_update_user(
                user_id=event_user.id,
                full_name=event_user.full_name or "Foydalanuvchi",
                username=event_user.username
            )
        return await handler(event, data)
