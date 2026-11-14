import re
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_menu_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """
    1. ASOSIY BOSH MENYU (3-rasm dizayni):
    - 1-qator: [ 🔎 𝗔𝗻𝗶𝗺𝗲 𝗶𝘇𝗹𝗮𝘀𝗵 ] (primary / ko'k)
    - 2-qator: [ 📄 𝗠𝗮𝗻𝗴𝗮 𝗸𝗼'𝗿𝗶𝘀𝗵 ] (primary / ko'k) | [ 🔴 𝗦𝗵𝗼𝗿𝘁𝘀 𝗸𝗼'𝗿𝗶𝘀𝗵 ] (danger / qizil)
    - 3-qator: [ 🗄 𝗞𝗮𝗯𝗶𝗻𝗲𝘁 ] (primary / ko'k) | [ 💎 𝗩𝗜𝗣 𝗢𝗯𝘂𝗻𝗮 ] (success / yashil)
    """
    builder = InlineKeyboardBuilder()

    # 1-qator: 🔎 Anime izlash
    builder.row(
        InlineKeyboardButton(
            text="🔎 𝗔𝗻𝗶𝗺𝗲 𝗶𝘇𝗹𝗮𝘀𝗵",
            switch_inline_query_current_chat="",
            style="primary"
        )
    )

    # 2-qator: 📄 Manga ko'rish | 🔴 Shorts ko'rish
    builder.row(
        InlineKeyboardButton(text="📄 𝗠𝗮𝗻𝗴𝗮 𝗸𝗼'𝗿𝗶𝘀𝗵", callback_data="btn_manga", style="primary"),
        InlineKeyboardButton(text="🔴 𝗦𝗵𝗼𝗿𝘁𝘀 𝗸𝗼'𝗿𝗶𝘀𝗵", callback_data="btn_shorts", style="danger")
    )

    # 3-qator: 🗄 Kabinet | 💎 VIP Obuna
    builder.row(
        InlineKeyboardButton(text="🗄 𝗞𝗮𝗯𝗶𝗻𝗲𝘁", callback_data="btn_cabinet", style="primary"),
        InlineKeyboardButton(text="💎 𝗩𝗜𝗣 𝗢𝗯𝘂𝗻𝗮", callback_data="btn_vip", style="success")
    )

    return builder.as_markup()


def get_anime_keyboard(anime_id: int, episodes_list: Optional[List[int]] = None) -> InlineKeyboardMarkup:
    """
    3. ANIME MENYUSI VA QISMLAR RO'YXATI (2-rasm dizayni):
    - Faqat admin yuklagan qismlar chiqadi.
    - Qismlar 4 tadan ustun (grid) ko'rinishida joylashadi (primary).
    - Eng pastki qatorda alohida keng tugma: ❌ Yopish (danger / qizil).
    """
    builder = InlineKeyboardBuilder()

    if episodes_list and len(episodes_list) > 0:
        # Faqat admin yuklagan qismlarni tartib bilan chiqarish
        sorted_episodes = sorted(list(set(episodes_list)))
        episode_buttons = []
        for ep in sorted_episodes:
            episode_buttons.append(
                InlineKeyboardButton(
                    text=f"▶️ {ep} - qism",
                    callback_data=f"play_{anime_id}_{ep}",
                    style="primary"
                )
            )

        # 4 tadan ustun (grid) qilib joylashtirish (2-rasmdagi ko'rinish)
        builder.add(*episode_buttons)
        builder.adjust(4)
    else:
        # Agar admin hali hech qanday qism yuklamagan bo'lsa
        builder.row(
            InlineKeyboardButton(
                text="⏳ Qismlar tez orada yuklanadi",
                callback_data="episodes_coming_soon",
                style="primary"
            )
        )

    # Eng pastki qatorda alohida keng tugma: ❌ Yopish (danger / qizil rangda)
    builder.row(
        InlineKeyboardButton(text="❌ 𝗬𝗼𝗽𝗶𝘀𝗵", callback_data="close_anime_view", style="danger")
    )

    return builder.as_markup()


def get_channel_post_keyboard(bot_username: str, anime_id: int) -> InlineKeyboardMarkup:
    """
    2. KANALGA AVTOMATIK POST TUGMALARI (1-rasm dizayni):
    1. ▶️ Tomosha qilish -> https://t.me/BOT_USERNAME?start=ANIME_ID (success / yashil)
    2. 📚 Barcha qismlar -> https://t.me/BOT_USERNAME?start=ANIME_ID (primary / ko'k)
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="▶️ 𝗧𝗼𝗺𝗼𝘀𝗵𝗮 𝗾𝗶𝗹𝗶𝘀𝗵",
            url=f"https://t.me/{bot_username}?start={anime_id}",
            style="success"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 𝗕𝗮𝗿𝗰𝗵𝗮 𝗾𝗶𝘀𝗺𝗹𝗮𝗿",
            url=f"https://t.me/{bot_username}?start={anime_id}",
            style="primary"
        )
    )

    return builder.as_markup()


def get_subscription_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Majburiy obuna sponsor kanallar tugmalari"""
    builder = InlineKeyboardBuilder()

    for idx, ch in enumerate(channels, 1):
        title = ch.get("title", f"Kanal #{idx}")
        link = ch.get("invite_link", "https://t.me")
        builder.row(
            InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary")
        )

    builder.row(
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription", style="success")
    )

    return builder.as_markup()


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Anime holatini tanlash (Admin)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Davom etmoqda", callback_data="status_davom", style="primary"),
        InlineKeyboardButton(text="Tugallangan", callback_data="status_tugallangan", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin asosiy paneli tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi anime qo'shish", callback_data="admin_add_anime", style="success"),
        InlineKeyboardButton(text="🎬 Qism yuklash", callback_data="admin_add_episode", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data="admin_delete_anime", style="danger"),
        InlineKeyboardButton(text="📢 Sponsor kanallar", callback_data="admin_channels", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="💎 VIP berish", callback_data="admin_give_vip", style="success"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast", style="primary")
    )
    return builder.as_markup()


def get_delete_confirm_keyboard(anime_id: int) -> InlineKeyboardMarkup:
    """Animeni o'chirishni tasdiqlash tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirilsin", callback_data=f"confirm_del_anime_{anime_id}", style="danger"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="primary")
    )
    return builder.as_markup()


def get_admin_cancel_keyboard() -> InlineKeyboardMarkup:
    """Bekor qilish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Kabinet ichidagi tugmalar"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 VIP sotib olish", callback_data="btn_vip", style="success"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="btn_cabinet", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home")
    )
    return builder.as_markup()


def get_back_home_keyboard() -> InlineKeyboardMarkup:
    """Faqat bosh menyuga qaytish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home", style="primary")
    )
    return builder.as_markup()


def get_vip_plans_keyboard() -> InlineKeyboardMarkup:
    """VIP tariflarini tanlash tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 𝟭 𝗼𝘆𝗹𝗶𝗸 — 𝟭𝟱,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_1", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="💎 𝟯 𝗼𝘆𝗹𝗶𝗸 — 𝟱𝟬,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_3", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="👑 𝗗𝗼𝗶𝗺𝗶𝘆 (𝗰𝗵𝗲𝗸𝘀𝗶𝘇) — 𝟭𝟬𝟬,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_unlimited", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="👨🏻‍💻 𝗔𝗱𝗺𝗶𝗻 𝗯𝗶𝗹𝗮𝗻 𝗯𝗼𝗴'𝗹𝗮𝗻𝗶𝘀𝗵", url="https://t.me/Jahongir02_02")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ 𝗕𝗼𝘀𝗵 𝗺𝗲𝗻𝘆𝘂", callback_data="btn_home")
    )
    return builder.as_markup()


def get_vip_payment_keyboard(plan_id: str, user_id: int) -> InlineKeyboardMarkup:
    """To'lov qilish va chek yuborish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 𝗖𝗵𝗲𝗸 (𝘀𝗸𝗿𝗶𝗻𝘀𝗵𝗼𝘁) 𝘆𝘂𝗯𝗼𝗿𝗶𝘀𝗵", callback_data=f"send_receipt_{plan_id}", style="success")
    )
    builder.row(
        InlineKeyboardButton(
            text="👨🏻‍💻 𝗔𝗱𝗺𝗶𝗻𝗴𝗮 𝘆𝗼𝘇𝗶𝘀𝗵",
            url=f"https://t.me/Jahongir02_02"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ 𝗕𝗼𝘀𝗵𝗾𝗮 𝘁𝗮𝗿𝗶𝗳 𝘁𝗮𝗻𝗹𝗮𝘀𝗵", callback_data="btn_vip")
    )
    return builder.as_markup()


def get_admin_vip_approval_keyboard(user_id: int, days: int) -> InlineKeyboardMarkup:
    """Admin uchun chekni tasdiqlash yoki rad etish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash (VIP berish)", callback_data=f"approve_vip_{user_id}_{days}", style="success"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_vip_{user_id}", style="danger")
    )
    return builder.as_markup()
