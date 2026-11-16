import html
import json
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    BusinessConnection,
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import db
from bot.config import config
from bot.keyboards import get_anime_keyboard

logger = logging.getLogger("AnimeBot.Business")
router = Router()


# ================= 1. TELEGRAM BUSINESS CONNECTION =================

@router.business_connection()
async def handle_business_connection(connection: BusinessConnection, bot: Bot):
    """Foydalanuvchi botni Telegram Business Chatbot sifatida ulaganda yoki o'chirganda"""
    user = connection.user
    user_id = user.id
    user_chat_id = connection.user_chat_id
    conn_id = connection.id
    is_enabled = connection.is_enabled
    can_reply = connection.can_reply

    data = {
        "first_name": user.first_name,
        "username": user.username,
        "rights": connection.rights.model_dump() if connection.rights else {},
        "date": connection.date.isoformat() if connection.date else None
    }

    await db.save_business_connection(
        connection_id=conn_id,
        user_id=user_id,
        user_chat_id=user_chat_id,
        can_reply=can_reply,
        is_enabled=is_enabled,
        data=data
    )

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    if is_enabled:
        text = (
            f"⚡️ <b>AniMovie UZ Business Chatbot faollashtirildi!</b>\n\n"
            f"Salom, <b>{html.escape(user.full_name)}</b>! Bot Telegram Business hisobingizga muvaffaqiyatli ulandi.\n\n"
            f"<b>Endi shaxsiy (user-to-user) 1-ga-1 chatlaringizda:</b>\n"
            f"• Suhbatdoshingiz anime kodi (masalan: <code>1</code>, <code>2</code>) yoki nomini yozsa, bot darhol o'sha chatga Ultra Glass Neon kartani chiqarib beradi.\n"
            f"• Qismlar tugmalari bosilganda video to'g'ridan-to'g'ri chatga yoki bot orqali yetkaziladi.\n"
            f"• Shuningdek, xohlagan chatda <code>@{bot_username} </code> orqali inline qidiruv ham to'liq ishlaydi!\n\n"
            f"<i>Sozlamalar: Telegram Sozlamalari ➔ Telegram Business ➔ Chatbotlar</i>"
        )
        try:
            await bot.send_message(chat_id=user_chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error sending business connection welcome: {e}")
    else:
        logger.info(f"Business connection {conn_id} disabled by user {user_id}")


# ================= 2. TELEGRAM BUSINESS MESSAGE (USER-TO-USER CHAT) =================

@router.business_message()
async def handle_business_activity(message: Message, bot: Bot):
    """
    Shaxsiy 1-ga-1 chatda (Telegram Business orqali) faollik yuz berganda
    oxirgi faol chatni eslab qolish va anime so'ralganda Ultra Glass Neon kartani chiqarish.
    """
    business_conn_id = message.business_connection_id
    if not business_conn_id:
        return

    # Faol 1-ga-1 business chatini eslab qolish (Inline va qismlar to'g'ridan-to'g'ri shu yerga yuborilishi uchun)
    try:
        conn = await db.get_business_connection(business_conn_id)
        if conn:
            owner_id = conn["user_id"]
            await db.record_business_chat(owner_id, business_conn_id, message.chat.id)
        if message.from_user:
            await db.record_business_chat(message.from_user.id, business_conn_id, message.chat.id)
        await db.record_business_chat(message.chat.id, business_conn_id, message.chat.id)
    except Exception as e:
        logger.warning(f"Error recording business chat: {e}")

    # Agar bot o'zi yuborgan xabar bo'lsa yoki matn bo'lmasa, to'xtatamiz
    if message.sender_business_bot or not message.text:
        return

    text = message.text.strip()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    target_anime = None

    # A) Faqat raqam bo'lsa (Anime ID: 1, 2, 3...)
    if text.isdigit():
        anime_id = int(text)
        target_anime = await db.get_anime(anime_id)

    # B) Maxsus komanda yoki trigger: /anime <nomi>, !anime <nomi>, anime <nomi>
    elif text.lower().startswith(("/anime", "!anime", "anime ")) or f"@{bot_username.lower()}" in text.lower():
        clean_query = text
        for prefix in ["/anime", "!anime", "anime", f"@{bot_username.lower()}"]:
            if clean_query.lower().startswith(prefix):
                clean_query = clean_query[len(prefix):].strip()
        if clean_query.isdigit():
            target_anime = await db.get_anime(int(clean_query))
        elif clean_query:
            results = await db.search_animes(clean_query, limit=1)
            if results:
                target_anime = results[0]

    # C) To'g'ridan-to'g'ri nom bo'lsa (aniq mos kelishini tekshirish)
    elif len(text) >= 3:
        results = await db.search_animes(text, limit=1)
        if results and (results[0]["title"].lower() in text.lower() or text.lower() in results[0]["title"].lower()):
            target_anime = results[0]

    if not target_anime:
        return

    # Ultra Glass Neon formatida kartani o'sha user-to-user chatiga yuborish
    anime_id = target_anime["id"]
    title = target_anime["title"]
    status = target_anime.get("status", "Davom etmoqda")
    genres = target_anime.get("genres", "Anime, Fantastika")
    channel = target_anime.get("channel", f"@{bot_username}")
    views = target_anime.get("views", 0)
    episodes_count = target_anime.get("episodes_count", "12")

    db_data = target_anime.get("data") or {}
    if isinstance(db_data, str):
        try:
            db_data = json.loads(db_data)
        except Exception:
            db_data = {}
    elif not isinstance(db_data, dict):
        db_data = {}

    alt_titles = db_data.get("alt_titles") or []
    alt_title = alt_titles[0] if (alt_titles and isinstance(alt_titles, list)) else ""

    ep_num = str(episodes_count).replace("qism", "").strip()
    ep_display = f"{ep_num} qism" if ep_num.isdigit() else str(episodes_count)

    st_clean = status.strip()
    status_badge = "🟢 Tugallangan" if "tugallan" in st_clean.lower() else "🔵 Davom etmoqda"

    genres_clean = ", ".join(w.strip().capitalize() for w in genres.replace("/", ",").split(",") if w.strip())
    if not genres_clean:
        genres_clean = "Anime, Fantastika"

    full_poster_url = f"https://ithac4290-sys.github.io/animoviebot/docs/posters/{anime_id}.jpg"

    caption = (
        f"<a href='{full_poster_url}'>&#8203;</a>"
        f"⚡️ <b>{html.escape(title.upper())}</b>\n"
        + (f"⟡ <i>{html.escape(alt_title)}</i> ⟡\n" if alt_title else "") +
        f"\n<blockquote>"
        f"╭── ✦ <b>ULTRA NEON EDITION</b> ✦ ──╮\n"
        f"│ 🌌 <b>Janr:</b> <code>{html.escape(genres_clean)}</code>\n"
        f"│ 💠 <b>Holati:</b> {status_badge}\n"
        f"│ 🔮 <b>Qismlar:</b> <code>{ep_display} [Full HD]</code>\n"
        f"│ ⚡️ <b>Sifat:</b> <code>1080p Ultra Clear</code>\n"
        f"│ 👁 <b>Ko'rishlar:</b> <code>{views:,} marta</code>\n"
        f"│ 📢 <b>Kanal:</b> {html.escape(channel)}\n"
        f"╰────────────────────────╯"
        f"</blockquote>\n\n"
        f"💎 <b>Anime ID:</b> <code>{anime_id}</code>  │  🍿 <b>Tomosha:</b> @{bot_username}"
    )

    episodes = await db.get_anime_episodes(anime_id)
    uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
    reply_markup = get_anime_keyboard(anime_id, uploaded_ep_nums)

    try:
        await message.answer(
            text=caption,
            business_connection_id=business_conn_id,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error sending business message: {e}")
