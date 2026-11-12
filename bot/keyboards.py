import re
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_menu_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """
    1. ASOSIY BOSH MENYU (3-rasm dizayni):
    - 1-qator: [ 🔎 Anime izlash ]
    - 2-qator: [ 📄 Manga kurish ] | [ 🔴 Shorts kurish ]
    - 3-qator: [ 🗄 Kabinet ] | [ 💎 VIP Obuna ]
    """
    builder = InlineKeyboardBuilder()

    # 1-qator: 🔎 Anime izlash (switch_inline_query_current_chat)
    builder.row(
        InlineKeyboardButton(
            text="🔎 Anime izlash",
            switch_inline_query_current_chat=""
        )
    )

    # 2-qator: 📄 Manga kurish | 🔴 Shorts kurish
    builder.row(
        InlineKeyboardButton(text="📄 Manga kurish", callback_data="btn_manga"),
        InlineKeyboardButton(text="🔴 Shorts kurish", callback_data="btn_shorts")
    )

    # 3-qator: 🗄 Kabinet | 💎 VIP Obuna
    builder.row(
        InlineKeyboardButton(text="🗄 Kabinet", callback_data="btn_cabinet"),
        InlineKeyboardButton(text="💎 VIP Obuna", callback_data="btn_vip")
    )

    return builder.as_markup()


def get_anime_keyboard(anime_id: int, episodes_count_str: str) -> InlineKeyboardMarkup:
    """
    3. ANIME MENYUSI VA QISMLAR RO'YXATI (2-rasm dizayni):
    - Qismlar soniga qarab tugmalar 4 tadan ustun (grid) ko'rinishida joylashsin.
    - Eng pastki qatorda alohida keng tugma: ❌ Yopish
    """
    builder = InlineKeyboardBuilder()

    # Qismlar sonini aniqlash (masalan "6 qism", "12", "24 qism" dan raqamni ajratib olish)
    match = re.search(r'\d+', str(episodes_count_str))
    total_episodes = int(match.group()) if match else 12

    # Agar qismlar soni juda ko'p bo'lsa (masalan 100+), me'yorida cheklash yoki barchasini ko'rsatish
    total_episodes = max(1, min(total_episodes, 200))

    episode_buttons = []
    for ep in range(1, total_episodes + 1):
        episode_buttons.append(
            InlineKeyboardButton(
                text=f"{ep} - qism",
                callback_data=f"play_{anime_id}_{ep}"
            )
        )

    # 4 tadan ustun (grid) qilib joylashtirish
    # Oxirgi qatordagi tugmalar avtomatik qolgan songa mos kengayadi
    builder.add(*episode_buttons)
    builder.adjust(4)

    # Eng pastki qatorda alohida keng tugma: ❌ Yopish
    builder.row(
        InlineKeyboardButton(text="❌ Yopish", callback_data="close_anime_view")
    )

    return builder.as_markup()


def get_channel_post_keyboard(bot_username: str, anime_id: int) -> InlineKeyboardMarkup:
    """
    2. KANALGA AVTOMATIK POST TUGMALARI (1-rasm dizayni):
    1. ▶️ Tomosha qilish -> https://t.me/BOT_USERNAME?start=ANIME_ID
    2. 📚 Barcha qismlar -> https://t.me/BOT_USERNAME?start=ANIME_ID
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="▶️ Tomosha qilish",
            url=f"https://t.me/{bot_username}?start={anime_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 Barcha qismlar",
            url=f"https://t.me/{bot_username}?start={anime_id}"
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
            InlineKeyboardButton(text=f"📢 {title}", url=link)
        )

    builder.row(
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
    )

    return builder.as_markup()


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Anime holatini tanlash (Admin)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Davom etmoqda", callback_data="status_davom"),
        InlineKeyboardButton(text="Tugallangan", callback_data="status_tugallangan")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")
    )
    return builder.as_markup()


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin asosiy paneli tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi anime qo'shish", callback_data="admin_add_anime"),
        InlineKeyboardButton(text="🎬 Qism yuklash", callback_data="admin_add_episode")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Sponsor kanallar", callback_data="admin_channels"),
        InlineKeyboardButton(text="💎 VIP berish", callback_data="admin_give_vip")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast")
    )
    return builder.as_markup()


def get_admin_cancel_keyboard() -> InlineKeyboardMarkup:
    """Bekor qilish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")
    )
    return builder.as_markup()


def get_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Kabinet ichidagi tugmalar"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 VIP sotib olish", callback_data="btn_vip"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="btn_cabinet")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home")
    )
    return builder.as_markup()


def get_back_home_keyboard() -> InlineKeyboardMarkup:
    """Faqat bosh menyuga qaytish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home")
    )
    return builder.as_markup()
