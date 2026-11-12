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


def get_anime_keyboard(anime_id: int, episodes_list: Optional[List[int]] = None) -> InlineKeyboardMarkup:
    """
    3. ANIME MENYUSI VA QISMLAR RO'YXATI (2-rasm dizayni):
    - Faqat admin yuklagan qismlar chiqadi (masalan admin 1-qismni qo'shganda 1-qism paydo bo'ladi).
    - Qismlar 4 tadan ustun (grid) ko'rinishida joylashadi.
    - Eng pastki qatorda alohida keng tugma: ❌ Yopish
    """
    builder = InlineKeyboardBuilder()

    if episodes_list and len(episodes_list) > 0:
        # Faqat admin yuklagan qismlarni tartib bilan chiqarish
        sorted_episodes = sorted(list(set(episodes_list)))
        episode_buttons = []
        for ep in sorted_episodes:
            episode_buttons.append(
                InlineKeyboardButton(
                    text=f"{ep} - qism",
                    callback_data=f"play_{anime_id}_{ep}"
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
                callback_data="episodes_coming_soon"
            )
        )

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
        InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data="admin_delete_anime"),
        InlineKeyboardButton(text="📢 Sponsor kanallar", callback_data="admin_channels")
    )
    builder.row(
        InlineKeyboardButton(text="💎 VIP berish", callback_data="admin_give_vip"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast")
    )
    return builder.as_markup()


def get_delete_confirm_keyboard(anime_id: int) -> InlineKeyboardMarkup:
    """Animeni o'chirishni tasdiqlash tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirilsin", callback_data=f"confirm_del_anime_{anime_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")
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
