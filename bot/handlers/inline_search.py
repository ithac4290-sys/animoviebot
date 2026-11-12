import html
from aiogram import Router, F, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineQueryResultPhoto
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
        # Eng ommabop top animelarni ko'rsatish
        results = await db.get_top_animes(limit=15)
    else:
        results = await db.search_animes(query, limit=15)

    inline_results = []

    for anime in results:
        anime_id = anime["id"]
        title = anime["title"]
        status = anime.get("status", "Davom etmoqda")
        episodes_count = anime.get("episodes_count", "12")
        channel = anime.get("channel", f"@{bot_username}")
        poster = anime.get("poster")

        caption = (
            f"{html.escape(title)}\n\n"
            f"<blockquote>• Holati: {html.escape(status)}\n"
            f"• Sifat - 720p, 1080p\n"
            f"• {html.escape(channel)}</blockquote>\n\n"
            f"🏷 Botimiz: @{bot_username}\n"
            f"📮 Anime ID: {anime_id}\n"
            f"📎 Link: https://t.me/{bot_username}?start={anime_id}"
        )

        episodes = await db.get_anime_episodes(anime_id)
        uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
        reply_markup = get_anime_keyboard(anime_id, uploaded_ep_nums)

        # Agar poster mavjud bo'lsa InlineQueryResultPhoto, aks holda Article
        if poster and not poster.startswith("http"):
            # Telegram file_id photo
            item = InlineQueryResultPhoto(
                id=str(anime_id),
                photo_file_id=poster,
                title=title,
                caption=caption,
                description=f"ID: {anime_id} | {episodes_count} | {status}",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            item = InlineQueryResultArticle(
                id=str(anime_id),
                title=title,
                description=f"ID: {anime_id} | {episodes_count} | {status}",
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
