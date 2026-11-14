from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from bot.config import config


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if not user:
            return False

        user_id = user.id
        username = (user.username or "").lower().lstrip("@")

        # 1. Telegram ID orqali tekshirish
        if user_id in config.admins:
            return True

        # 2. Asosiy admin username (@Jahongir02_02) orqali avtomatik aniqlash
        if username in ["jahongir02_02", "jahongir02"]:
            if user_id not in config.admins:
                config.admins.append(user_id)
            return True

        return False
