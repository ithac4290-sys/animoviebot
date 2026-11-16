import html
import json
from aiogram import Router, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from bot.database import db
from bot.config import config
from bot.keyboards import get_anime_keyboard

router = Router()


@router.inline_query()
async def handle_inline_search(inline_query: InlineQuery, bot: Bot):
    query = inline_query.query.strip()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    if not query:
        # Eng ommabop animelarni ko'rsatish
        results = await db.get_top_animes(limit=20)
    else:
        results = await db.search_animes(query, limit=20)

    inline_results = []

    for anime in results:
        anime_id = anime["id"]
        title = anime["title"]
        status = anime.get("status", "Davom etmoqda")
        genres = anime.get("genres", "Anime, Fantastika")
        channel = anime.get("channel", f"@{bot_username}")
        views = anime.get("views", 0)
        episodes_count = anime.get("episodes_count", "12")

        db_data = anime.get("data") or {}
        if isinstance(db_data, str):
            try:
                db_data = json.loads(db_data)
            except Exception:
                db_data = {}
        elif not isinstance(db_data, dict):
            db_data = {}

        alt_titles = db_data.get("alt_titles") or []
        alt_title = alt_titles[0] if (alt_titles and isinstance(alt_titles, list)) else ""

        # Pop-up ro'yxatida ko'rinadigan sarlavha va tavsif
        display_title = f"🎬 {title}"
        if alt_title:
            display_title += f" • {alt_title}"

        description = f"⭐ {episodes_count} | {genres} | {status}"
        thumbnail_url = f"https://ithac4290-sys.github.io/animoviebot/docs/posters/{anime_id}.jpg"

        # Xabar yuborilgandagi dizayn (rasmli va batafsil)
        caption = (
            f"<a href='{thumbnail_url}'>&#8203;</a>"
            f"🎬 <b>{html.escape(title)}</b>\n"
            + (f"<i>({html.escape(alt_title)})</i>\n" if alt_title else "") +
            f"\n<blockquote>"
            f"🎭 <b>Janr:</b> {html.escape(genres)}\n"
            f"📌 <b>Holati:</b> {html.escape(status)}\n"
            f"⚡️ <b>Sifat:</b> 720p / 1080p FULL HD\n"
            f"👁 <b>Ko'rishlar:</b> {views} marta\n"
            f"📢 <b>Kanal:</b> {html.escape(channel)}"
            f"</blockquote>\n\n"
            f"📮 <b>Anime ID:</b> <code>{anime_id}</code>\n"
            f"🍿 <b>Tomosha qilish:</b> @{bot_username}"
        )

        episodes = await db.get_anime_episodes(anime_id)
        uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
        reply_markup = get_anime_keyboard(anime_id, uploaded_ep_nums)

        # Telegram vertikal zamonaviy ro'yxat dizayni (Article mode with thumbnail)
        item = InlineQueryResultArticle(
            id=str(anime_id),
            title=display_title,
            description=description,
            thumbnail_url=thumbnail_url,
            thumbnail_width=100,
            thumbnail_height=140,
            input_message_content=InputTextMessageContent(
                message_text=caption,
                parse_mode="HTML"
            ),
            reply_markup=reply_markup
        )
        inline_results.append(item)

    await inline_query.answer(
        results=inline_results,
        cache_time=5,
        is_personal=True
    )
