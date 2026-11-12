from typing import List, Dict, Any, Tuple
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from bot.database import db
from bot.config import config


async def check_user_subscriptions(bot: Bot, user_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Foydalanuvchi majburiy obuna kanallariga a'zo ekanligini tekshiradi.
    Adminlar va VIP foydalanuvchilar tekshiruvdan ozod etiladi.
    Qaytaradi: (is_subscribed: bool, unsubscribed_channels: list)
    """
    # 1. Adminlar uchun tekshiruv yo'q
    if user_id in config.admins:
        return True, []

    # 2. VIP statusga ega foydalanuvchilar uchun tekshiruv yo'q
    if await db.check_user_vip_status(user_id):
        return True, []

    # 3. Bazadagi faol sponsor kanallarni olish
    channels = await db.get_active_sponsor_channels()
    if not channels:
        return True, []

    unsubscribed: List[Dict[str, Any]] = []

    for channel in channels:
        channel_id = channel.get("channel_id")
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in [
                ChatMemberStatus.LEFT,
                ChatMemberStatus.KICKED,
                ChatMemberStatus.RESTRICTED
            ]:
                unsubscribed.append(channel)
        except Exception:
            # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa,
            # foydalanuvchini bloklamaslik uchun yoki havolasini ko'rsatish
            unsubscribed.append(channel)

    if unsubscribed:
        return False, unsubscribed

    return True, []
