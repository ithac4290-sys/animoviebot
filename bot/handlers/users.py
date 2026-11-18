import html
import json
import logging
import re
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import config
from bot.database import db
from bot.keyboards import (
    get_main_menu_keyboard,
    get_anime_keyboard,
    get_anime_seasons_keyboard,
    get_subscription_keyboard,
    get_cabinet_keyboard,
    get_back_home_keyboard,
    get_vip_plans_keyboard,
    get_vip_payment_keyboard,
    get_admin_vip_approval_keyboard,
    get_search_type_keyboard,
    get_genres_keyboard,
    get_animes_pagination_keyboard,
    get_search_cancel_keyboard,
    get_ai_image_confirmation_keyboard,
    get_ai_image_retry_keyboard
)
from bot.gemini_search import (
    identify_anime,
    match_anime_in_database,
    ensure_multilingual_titles,
    has_cyrillic
)
from bot.states import VipPaymentState, UserSearchState
from bot.utils import check_user_subscriptions

router = Router()
logger = logging.getLogger(__name__)


def get_welcome_text(full_name: str) -> str:
    """Bosh sahifa xush kelibsiz matni"""
    escaped_name = html.escape(full_name or "Foydalanuvchi")
    return (
        f"👋🏻 <b>Assalomu alaykum, hurmatli '{escaped_name}'!</b>\n"
        f"<b>AniMovieUZ rasmiy botiga xush kelibsiz!</b>\n\n"
        f"🍿 <i>Botimizda barcha sara animelarni osongina @Ani_Movei_UZ kanalidan yuklab olib tomosha qilishingiz mumkin.</i>\n\n"
        f"<u>⚡️ Botimizdagi asosiy buyruqlar:</u>\n"
        f"<blockquote>🎬 /top — Eng ommabop animelar ro'yxati\n"
        f"👨🏻‍💻 /help — Qo'llab-quvvatlash xizmati\n"
        f"👑 /vip — VIP Obuna va imtiyozlar\n"
        f"🤝 /homiy — Homiy bo'lish (O'z botingizni ulash)\n"
        f"💡 /qollanma — Botdan foydalanish qo'llanmasi</blockquote>\n\n"
        f"🔥 <b>Botga to'g'ridan-to'g'ri anime kodi yoki nomini yozishingiz mumkin.</b>"
    )


def format_anime_caption(anime: dict, bot_username: str) -> str:
    """Anime card zamonaviy caption dizayni"""
    title = html.escape(anime.get("title", ""))
    status = html.escape(anime.get("status", "Davom etmoqda"))
    genres = html.escape(anime.get("genres", "Anime, Fantastika"))
    channel = html.escape(anime.get("channel", f"@{bot_username}"))
    anime_id = anime.get("id")
    views = anime.get("views", 0)

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
    alt_line = f"<i>({html.escape(alt_title)})</i>\n" if alt_title else ""

    return (
        f"🎬 <b>{title}</b>\n"
        f"{alt_line}\n"
        f"<blockquote>"
        f"🎭 <b>Janr:</b> {genres}\n"
        f"📌 <b>Holati:</b> {status}\n"
        f"⚡️ <b>Sifat:</b> 720p / 1080p FULL HD\n"
        f"👁 <b>Ko'rishlar:</b> {views} marta\n"
        f"📢 <b>Kanal:</b> {channel}"
        f"</blockquote>\n\n"
        f"📮 <b>Anime ID:</b> <code>{anime_id}</code>\n"
        f"🍿 <b>Tomosha qilish:</b> @{bot_username}"
    )


# ================= /start BUYRUG'I =================

@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext):
    await state.clear()
    args = command.args
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    # Agar parametr bo'lsa (Deep-link: masalan /start 961 yoki /start manga_1)
    if args:
        clean_arg = args.strip()
        if clean_arg.startswith("manga_"):
            m_id = clean_arg.replace("manga_", "")
            if m_id.isdigit():
                await show_manga_by_id(message, int(m_id), bot, bot_username)
                return

        # "play_1_1" (Inline xabardan yoki havoladan qismni ko'rish)
        if clean_arg.startswith("play_"):
            parts = clean_arg.split("_")
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                a_id = int(parts[1])
                e_num = int(parts[2])
                await send_episode_direct(message, a_id, e_num, bot, bot_username)
                return

        # "anime_961" yoki "961"
        if clean_arg.startswith("anime_"):
            clean_arg = clean_arg.replace("anime_", "")

        if clean_arg.isdigit():
            anime_id = int(clean_arg)
            await show_anime_by_id(message, anime_id, bot, bot_username)
            return

    # Parametr bo'lmaganda: ASOSIY BOSH MENYU (3-rasm dizayni)
    user_id = message.from_user.id
    is_vip = (user_id in config.admins) or await db.check_user_vip_status(user_id)
    text = get_welcome_text(message.from_user.full_name)
    kb = get_main_menu_keyboard(bot_username, is_vip=is_vip, user_id=user_id)
    await message.answer(text=text, reply_markup=kb, parse_mode="HTML")


# ================= ANIME FASLLARI VA KO'RISH LOGIKASI =================

def extract_base_anime_title(title: str) -> str:
    """Anime nomidan fasl qismini (masalan, 1-fasl, Season 2) ajratib olib, asosiy nomni qaytaradi"""
    patterns = [
        r'[\(\[\s\-_]+(\d+)[\s\-_]*(?:fasl|mavsum|sezon|season)[\)\]\s\-_]*',
        r'[\(\[\s\-_]+(?:fasl|mavsum|sezon|season)[\s\-_]*(\d+)[\)\]\s\-_]*',
        r'[\(\[\s\-_]+S(\d+)[\)\]\s\-_]*',
    ]
    clean_title = title
    for p in patterns:
        clean_title = re.sub(p, '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[\(\[\{\-_:]+$', '', clean_title).strip()
    return clean_title or title


def extract_season_num(title: str) -> int:
    """Anime sarlavhasidan fasl raqamini aniqlash (standart 1)"""
    patterns = [
        r'[\(\[\s\-_]+(\d+)[\s\-_]*(?:fasl|mavsum|sezon|season)[\)\]\s\-_]*',
        r'[\(\[\s\-_]+(?:fasl|mavsum|sezon|season)[\s\-_]*(\d+)[\)\]\s\-_]*',
        r'[\(\[\s\-_]+S(\d+)[\)\]\s\-_]*',
    ]
    for p in patterns:
        m = re.search(p, title, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return 1


async def get_anime_seasons_map(anime_id: int):
    """Anime uchun mavjud barcha fasllarni bazadan aniqlash va xaritasini qaytarish"""
    anime = await db.get_anime(anime_id)
    if not anime:
        return {1: anime_id, 2: None}, ""
    title = anime.get("title", "")
    base_title = extract_base_anime_title(title)

    # Bazadan ushbu nomga mos barcha fasllarni qidirish
    all_animes = await db.search_animes(base_title, limit=20)
    seasons_map = {}
    for a in all_animes:
        a_title = a.get("title", "")
        if extract_base_anime_title(a_title).lower() == base_title.lower():
            s_num = extract_season_num(a_title)
            seasons_map[s_num] = a["id"]

    # Har doim 1-fasl mavjud bo'lishini ta'minlash
    if 1 not in seasons_map:
        seasons_map[1] = anime_id

    # Har doim kamida 1-fasl va 2-fasl tanlovi bo'lishini ta'minlash
    if 2 not in seasons_map:
        seasons_map[2] = None

    return seasons_map, base_title


def format_anime_season_caption(anime: dict, bot_username: str, base_title: str) -> str:
    """Fasl tanlash oynasi uchun Ultra Glass Neon dizaynidagi matn"""
    title = html.escape(base_title or anime.get("title", ""))
    status = html.escape(anime.get("status", "Davom etmoqda"))
    genres = html.escape(anime.get("genres", "Anime, Fantastika"))
    channel = html.escape(anime.get("channel", f"@{bot_username}"))
    views = anime.get("views", 0)

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
    alt_line = f"│  ✨ <i>({html.escape(alt_title)})</i>\n" if alt_title else ""

    return (
        "╭── ✦ <b>FASLNI TANLANG</b> ✦ ──╮\n"
        "│\n"
        f"│  🎬 <b>Anime:</b> {title}\n"
        f"{alt_line}"
        f"│  🎭 <b>Janr:</b> {genres}\n"
        f"│  📌 <b>Holati:</b> {status}\n"
        f"│  ⚡️ <b>Sifat:</b> Full HD 1080p\n"
        f"│  👁 <b>Ko'rishlar:</b> {views} marta\n"
        f"│  📢 <b>Kanal:</b> {channel}\n"
        "│\n"
        "╰────────────────────────╯\n\n"
        "🍿 <b>Qaysi faslni tomosha qilmoqchisiz?</b>\n"
        "<i>Quyidagi fasllardan birini tanlang:</i>"
    )


async def show_anime_seasons_menu(message_or_query, anime_id: int, bot: Bot, bot_username: str):
    """Foydalanuvchiga anime nomi va 1-fasl / 2-fasl tanlash menyusini chiqarish"""
    user_id = message_or_query.from_user.id
    is_message = isinstance(message_or_query, Message)

    # 1. Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        text = (
            "⚠️ <b>Kechirasiz, anime tomosha qilish uchun quyidagi homiy kanallarimizga obuna bo'lishingiz kerak:</b>\n\n"
            "<i>Iltimos, kanallarga a'zo bo'lib, '✅ Obunani tekshirish' tugmasini bosing!</i>"
        )
        builder = InlineKeyboardBuilder()
        for idx, ch in enumerate(unsubbed, 1):
            title = ch.get("title", f"Kanal #{idx}")
            link = ch.get("invite_link", "https://t.me")
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary"))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{anime_id}", style="success"))
        kb = builder.as_markup()
        if is_message:
            await message_or_query.answer(text=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
        return

    # 2. Anime ma'lumotlarini olish
    anime = await db.get_anime(anime_id)
    if not anime:
        not_found_text = f"❌ <b>Kechirasiz, {anime_id} ID raqamli anime topilmadi!</b>"
        if is_message:
            await message_or_query.answer(not_found_text, parse_mode="HTML")
        else:
            await message_or_query.answer(not_found_text, show_alert=True)
        return

    seasons_map, base_title = await get_anime_seasons_map(anime_id)
    caption = format_anime_season_caption(anime, bot_username, base_title)
    kb = get_anime_seasons_keyboard(anime_id, seasons_map)
    poster = anime.get("poster")

    if is_message:
        if poster:
            await message_or_query.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.answer(text=caption, reply_markup=kb, parse_mode="HTML")
    else:
        # CallbackQuery
        try:
            if message_or_query.message and message_or_query.message.photo:
                await message_or_query.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                await message_or_query.message.edit_text(text=caption, reply_markup=kb, parse_mode="HTML")
        except Exception:
            if poster:
                await message_or_query.message.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                await message_or_query.message.answer(text=caption, reply_markup=kb, parse_mode="HTML")


async def show_anime_by_id(message_or_query, anime_id: int, bot: Bot, bot_username: str):
    """Tanlangan fasl yoki animeni to'liq qismlar menyusi bilan ko'rsatish"""
    user_id = message_or_query.from_user.id
    is_message = isinstance(message_or_query, Message)

    # 1. Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        text = (
            "⚠️ <b>Kechirasiz, anime tomosha qilish uchun quyidagi homiy kanallarimizga obuna bo'lishingiz kerak:</b>\n\n"
            "<i>Iltimos, kanallarga a'zo bo'lib, '✅ Obunani tekshirish' tugmasini bosing!</i>"
        )
        builder = InlineKeyboardBuilder()
        for idx, ch in enumerate(unsubbed, 1):
            title = ch.get("title", f"Kanal #{idx}")
            link = ch.get("invite_link", "https://t.me")
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary"))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{anime_id}", style="success"))
        kb = builder.as_markup()

        if is_message:
            await message_or_query.answer(text=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
        return

    # 2. Bazadan animeni olish
    anime = await db.get_anime(anime_id)
    if not anime:
        not_found_text = f"❌ <b>Kechirasiz, {anime_id} ID raqamli anime topilmadi!</b>"
        if is_message:
            await message_or_query.answer(not_found_text, parse_mode="HTML")
        else:
            await message_or_query.answer(not_found_text, show_alert=True)
        return

    # Ko'rishlar sonini oshirish
    await db.increment_anime_views(anime_id)

    caption = format_anime_caption(anime, bot_username)

    # Faqat admin yuklagan qismlar ro'yxatini olish
    episodes = await db.get_anime_episodes(anime_id)
    uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
    kb = get_anime_keyboard(anime_id, uploaded_ep_nums)

    poster = anime.get("poster")
    if is_message:
        if poster:
            await message_or_query.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.answer(text=caption, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            if message_or_query.message and message_or_query.message.photo:
                await message_or_query.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                await message_or_query.message.edit_text(text=caption, reply_markup=kb, parse_mode="HTML")
        except Exception:
            if poster:
                await message_or_query.message.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                await message_or_query.message.answer(text=caption, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("open_season_"))
async def handle_open_season_callback(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    target_id = int(parts[2])
    season_num = int(parts[3])
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    await callback.answer(f"🍿 {season_num}-fasl ochilmoqda...", show_alert=False)
    await show_anime_by_id(callback, target_id, bot, bot_username)


@router.callback_query(F.data.startswith("season_unavailable_"))
async def handle_season_unavailable_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    season_num = parts[3] if len(parts) > 3 else "2"
    await callback.answer(
        f"⏳ Ushbu animening {season_num}-fasli tez kunda kanalimiz va botimizga joylanadi!",
        show_alert=True
    )


@router.callback_query(F.data.startswith("show_seasons_"))
async def handle_show_seasons_callback(callback: CallbackQuery, bot: Bot):
    anime_id = int(callback.data.replace("show_seasons_", ""))
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    await callback.answer()
    await show_anime_seasons_menu(callback, anime_id, bot, bot_username)


@router.callback_query(F.data == "episodes_coming_soon")
async def handle_episodes_coming_soon(callback: CallbackQuery):
    await callback.answer("⏳ Ushbu animening qismlari tez kunda yuklanadi!", show_alert=True)


async def send_episode_direct(message: Message, anime_id: int, ep_num: int, bot: Bot, bot_username: str):
    """Deep-link yoki inline rejimdan to'g'ridan-to'g'ri qismni yuborish"""
    user_id = message.from_user.id
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        text = (
            "⚠️ <b>Anime ko'rish uchun homiy kanallarga obuna bo'lishingiz zarur:</b>\n\n"
            "<i>Iltimos, quyidagi kanallarga obuna bo'lib, '✅ Obunani tekshirish' tugmasini bosing:</i>"
        )
        builder = InlineKeyboardBuilder()
        for idx, ch in enumerate(unsubbed, 1):
            title = ch.get("title", f"Kanal #{idx}")
            link = ch.get("invite_link", "https://t.me")
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary"))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_play_{anime_id}_{ep_num}", style="success"))
        await message.answer(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return

    anime = await db.get_anime(anime_id)
    episode = await db.get_episode(anime_id, ep_num)
    if not episode:
        await message.answer(f"⚠️ <b>{anime_id}-ID li animening {ep_num}-qismi hali yuklanmagan!</b>", parse_mode="HTML")
        return

    anime_title = anime.get("title", "Anime") if anime else "Anime"
    file_id = episode.get("file_id")
    file_type = episode.get("file_type", "video")

    video_caption = (
        f"🎬 <b>{html.escape(anime_title)}</b> - {ep_num}-qism\n\n"
        f"🏷 Botimiz: @{bot_username}\n"
        f"📮 Anime ID: {anime_id}"
    )

    episodes = await db.get_anime_episodes(anime_id)
    uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
    kb = get_anime_keyboard(anime_id, uploaded_ep_nums, current_ep=ep_num)

    try:
        if file_type == "document":
            await bot.send_document(
                chat_id=user_id,
                document=file_id,
                caption=video_caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await bot.send_video(
                chat_id=user_id,
                video=file_id,
                caption=video_caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error sending episode direct: {e}")
        await message.answer(f"❌ Videoni yuborishda xatolik yuz berdi: {str(e)}")


# ================= QISM TUGMASI BOSILGANDA =================

@router.callback_query(F.data.startswith("play_"))
async def handle_play_episode(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_inline = bool(callback.inline_message_id)

    # Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        await callback.answer("⚠️ Iltimos, oldin kanallarga a'zo bo'ling!", show_alert=True)
        if not is_inline and callback.message:
            kb = get_subscription_keyboard(unsubbed)
            await callback.message.answer(
                "⚠️ <b>Anime ko'rish uchun homiy kanallarga obuna bo'lishingiz zarur:</b>",
                reply_markup=kb,
                parse_mode="HTML"
            )
        return

    parts = callback.data.split("_")
    anime_id = int(parts[1])
    ep_num = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else ((ep_num - 1) // 20 + 1)

    anime = await db.get_anime(anime_id)
    episode = await db.get_episode(anime_id, ep_num)

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    if not episode:
        await callback.answer(f"⚠️ {ep_num}-qism tez orada yuklanadi!", show_alert=True)
        return

    # Tanlangan qism belgisini klaviaturada yangilash ([ 📀 ] - {ep_num})
    try:
        episodes = await db.get_anime_episodes(anime_id)
        uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
        updated_kb = get_anime_keyboard(anime_id, uploaded_ep_nums, page=page, current_ep=ep_num)
        if is_inline:
            await bot.edit_message_reply_markup(
                inline_message_id=callback.inline_message_id,
                reply_markup=updated_kb
            )
        elif callback.message:
            await callback.message.edit_reply_markup(reply_markup=updated_kb)
    except Exception:
        pass

    anime_title = anime.get("title", "Anime") if anime else "Anime"
    file_id = episode.get("file_id")
    file_type = episode.get("file_type", "video")

    video_caption = (
        f"🎬 <b>{html.escape(anime_title)}</b> - {ep_num}-qism\n\n"
        f"🏷 Botimiz: @{bot_username}\n"
        f"📮 Anime ID: {anime_id}"
    )

    # 1. Telegram Business 1-ga-1 chat tekshiruvi:
    # Agar xabar business connection orqali kelgan bo'lsa yoki foydalanuvchi faol business chatda bo'lsa:
    biz_conn_id = None
    biz_chat_id = None

    if callback.message and getattr(callback.message, "business_connection_id", None):
        biz_conn_id = callback.message.business_connection_id
        biz_chat_id = callback.message.chat.id
    elif is_inline:
        active_chat = await db.get_active_business_chat(user_id)
        if active_chat:
            biz_conn_id = active_chat.get("connection_id")
            biz_chat_id = active_chat.get("chat_id")

    # Agar 1-ga-1 Telegram Business chatda bo'lsa, to'g'ridan-to'g'ri o'sha chatga video yuboramiz!
    if biz_conn_id and biz_chat_id:
        try:
            if file_type == "document":
                await bot.send_document(
                    business_connection_id=biz_conn_id,
                    chat_id=biz_chat_id,
                    document=file_id,
                    caption=video_caption,
                    parse_mode="HTML"
                )
            else:
                await bot.send_video(
                    business_connection_id=biz_conn_id,
                    chat_id=biz_chat_id,
                    video=file_id,
                    caption=video_caption,
                    parse_mode="HTML"
                )
            await callback.answer(f"✅ {ep_num}-qism to'g'ridan-to'g'ri ushbu chatga yuborildi!", show_alert=False)
            return
        except Exception as e:
            logger.warning(f"Could not send video via business connection {biz_conn_id} to chat {biz_chat_id}: {e}")

    # 2. Agar business chat bo'lmasa yoki jo'natib bo'lmasa, odatdagi shaxsiy bot chatiga yuborish:
    try:
        if file_type == "document":
            await bot.send_document(
                chat_id=user_id,
                document=file_id,
                caption=video_caption,
                parse_mode="HTML"
            )
        else:
            await bot.send_video(
                chat_id=user_id,
                video=file_id,
                caption=video_caption,
                parse_mode="HTML"
            )
        await callback.answer(f"✅ {ep_num}-qism shaxsiyingizga yuborildi!", show_alert=False)
    except Exception as e:
        logger.warning(f"Could not send video directly to user {user_id}: {e}")
        # Foydalanuvchi botni start qilmagan bo'lsa (yoki user-to-user inline bo'lsa)
        await callback.answer(
            url=f"https://t.me/{bot_username}?start=play_{anime_id}_{ep_num}"
        )


# ================= ❌ YOPISH TUGMASI =================

@router.callback_query(F.data == "close_anime_view")
async def handle_close_view(callback: CallbackQuery, bot: Bot):
    if callback.inline_message_id:
        try:
            await bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text="❌ <i>Anime ko'rish oynasi yopildi.</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    elif callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer("Yopildi.")


# ================= ⏩ QISMLARNI SAHIFALASH (PAGINATION) =================

@router.callback_query(F.data.startswith("ep_page_"))
async def handle_episodes_page(callback: CallbackQuery, bot: Bot):
    """20 tadan oshganda qismlarni sahifalab ko'rsatish (Oldingi / Keyingi tugmalari)"""
    parts = callback.data.split("_")
    # Format: ep_page_{anime_id}_{page}_{current_ep}
    anime_id = int(parts[2])
    page = int(parts[3])
    current_ep = int(parts[4]) if len(parts) > 4 else None

    episodes = await db.get_anime_episodes(anime_id)
    uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
    kb = get_anime_keyboard(anime_id, uploaded_ep_nums, page=page, current_ep=current_ep)

    try:
        if callback.inline_message_id:
            await bot.edit_message_reply_markup(
                inline_message_id=callback.inline_message_id,
                reply_markup=kb
            )
        elif callback.message:
            await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "ep_first_page_alert")
async def handle_ep_first_page_alert(callback: CallbackQuery):
    await callback.answer("ℹ️ Siz allaqachon birinchi sahifadasiz!", show_alert=False)


@router.callback_query(F.data == "ep_last_page_alert")
async def handle_ep_last_page_alert(callback: CallbackQuery):
    await callback.answer("ℹ️ Siz oxirgi sahifadasiz!", show_alert=False)


@router.callback_query(F.data == "noop_page")
async def handle_noop_page(callback: CallbackQuery):
    await callback.answer("📄 Sahifa indikatori")


# ================= QIDIRUV MENYUSI VA TURLARI (Rasm dizayni) =================

@router.callback_query(F.data == "btn_search_menu")
async def handle_search_menu(callback: CallbackQuery, state: FSMContext):
    """Qidiruv tipini tanlash menyusi (foydalanuvchi yuborgan rasm dizayni)"""
    await state.clear()
    await callback.answer()
    text = "🔍 <b>Qidiruv tipini tanlang :</b>"
    try:
        await callback.message.edit_text(text, reply_markup=get_search_type_keyboard(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=get_search_type_keyboard(), parse_mode="HTML")


# 1. 🏷 Anime nomi orqali qidirish
@router.callback_query(F.data == "search_by_name")
async def handle_search_by_name_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserSearchState.by_name)
    text = (
        "🏷 <b>Anime nomi orqali qidirish</b>\n\n"
        "Qidirmoqchi bo'lgan anime nomini yozing:\n"
        "<i>(Masalan: Naruto yoki Titan)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_search_cancel_keyboard(), parse_mode="HTML")


@router.message(UserSearchState.by_name)
async def process_search_by_name(message: Message, state: FSMContext, bot: Bot):
    query = message.text.strip()
    await state.clear()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    results = await db.search_animes(query, limit=10)
    if not results:
        await message.answer(
            f"❌ <b>'{html.escape(query)}'</b> nomli anime topilmadi.\n\n"
            f"<i>Boshqa nom bilan qidirib ko'ring yoki quyidagi menyudan foydalaning:</i>",
            reply_markup=get_search_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    if len(results) == 1:
        await show_anime_seasons_menu(message, results[0]["id"], bot, bot_username)
        return

    text = f"🔎 <b>'{html.escape(query)}'</b> bo'yicha topilgan animelar:\n\n<i>Kerakli animeni tanlang:</i>"
    kb = get_animes_pagination_keyboard(results, 0, 1)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# 2. 📌 Kod orqali qidirish
@router.callback_query(F.data == "search_by_code")
async def handle_search_by_code_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserSearchState.by_code)
    text = (
        "📌 <b>Kod orqali qidirish</b>\n\n"
        "Anime kodini (ID raqamini) kiriting:\n"
        "<i>(Masalan: 1 yoki 961)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_search_cancel_keyboard(), parse_mode="HTML")


@router.message(UserSearchState.by_code)
async def process_search_by_code(message: Message, state: FSMContext, bot: Bot):
    query = message.text.strip()
    if not query.isdigit():
        await message.answer(
            "❌ Anime kodi faqat raqamlardan iborat bo'lishi kerak. Masalan: 1",
            reply_markup=get_search_cancel_keyboard()
        )
        return

    await state.clear()
    anime_id = int(query)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    await show_anime_by_id(message, anime_id, bot, bot_username)


# 3. ⏱ So'ngi yuklanganlar
@router.callback_query(F.data == "search_latest")
async def handle_search_latest(callback: CallbackQuery):
    await callback.answer()
    animes = await db.get_latest_animes(limit=10)
    if not animes:
        await callback.answer("Hozircha animelar yuklanmagan.", show_alert=True)
        return

    text = "⏱ <b>So'ngi yuklangan animelar:</b>\n\n<i>Kerakli animeni tanlang:</i>"
    kb = get_animes_pagination_keyboard(animes, 0, 1)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# 4. 💬 Janr orqali qidirish
@router.callback_query(F.data == "search_genres")
async def handle_search_genres_menu(callback: CallbackQuery):
    await callback.answer()
    text = "💬 <b>Janr orqali qidirish:</b>\n\nQaysi janrdagi animelarni tomosha qilmoqchisiz?"
    try:
        await callback.message.edit_text(text, reply_markup=get_genres_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=get_genres_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("genre_"))
async def handle_genre_selected(callback: CallbackQuery):
    await callback.answer()
    genre_name = callback.data.replace("genre_", "")
    animes = await db.search_animes_by_genre(genre_name, limit=10)

    if not animes:
        await callback.answer(f"❌ '{genre_name}' janrida hali anime qo'shilmagan.", show_alert=True)
        return

    text = f"💬 <b>{html.escape(genre_name)}</b> janridagi animelar:\n\n<i>Kerakli animeni tanlang:</i>"
    kb = get_animes_pagination_keyboard(animes, 0, 1)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# 5. 👁 Eng ko'p ko'rilgan
@router.callback_query(F.data == "search_top_views")
async def handle_search_top_views(callback: CallbackQuery):
    await callback.answer()
    top_animes = await db.get_top_animes(limit=10)
    if not top_animes:
        await callback.answer("Hozircha animelar yo'q.", show_alert=True)
        return

    text = "👁 <b>Eng ko'p ko'rilgan TOP animelar:</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    builder = InlineKeyboardBuilder()

    for idx, a in enumerate(top_animes):
        badge = medals[idx] if idx < len(medals) else "▫️"
        views = a.get("views", 0)
        text += f"{badge} <b>{html.escape(a['title'])}</b> — <i>{views} marta ko'rilgan</i>\n"
        builder.row(InlineKeyboardButton(text=f"{badge} {a['title'][:25]}", callback_data=f"open_anime_{a['id']}", style="primary"))

    builder.row(
        InlineKeyboardButton(text="⬅️ Qidiruv menyusi", callback_data="btn_search_menu", style="danger"),
        InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="btn_home", style="danger")
    )
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# 6. 🖼 Rasm orqali qidirish
@router.callback_query(F.data == "search_by_image")
async def handle_search_by_image_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserSearchState.by_image)
    text = (
        "🖼 <b>Rasm orqali qidirish</b>\n\n"
        "Anime skrinshotini yoki posterini (rasm ko'rinishida) yuboring:\n"
        "<i>Bot rasm orqali qaysi anime ekanligini aniqlashga harakat qiladi va bazamizdan topib beradi.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_search_cancel_keyboard(), parse_mode="HTML")


@router.message(StateFilter(UserSearchState.by_image, None), F.photo)
async def process_search_by_image(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    status_msg = await message.answer(
        "🔍 <b>AI rasm tahlili boshlandi...</b>\n"
        "<i>Surat tahlil qilinib, web qidiruv va bazamiz bilan solishtirilmoqda, iltimos kuting.</i>",
        parse_mode="HTML"
    )

    photo = message.photo[-1]

    try:
        from io import BytesIO
        from bot.image_search import compute_image_hash, hash_similarity

        photo_bytes_io = BytesIO()
        await bot.download(photo, destination=photo_bytes_io)
        image_data = photo_bytes_io.getvalue()

        # 1-BOSQICH: GEMINI MULTIMODAL VA WEB QIDIRUV ORQALI ANIMENI ANIQLASH (3 TILDA)
        detected_info = await identify_anime(
            image_bytes=image_data,
            gemini_key=config.gemini_api_key,
            trace_key=config.trace_moe_api_key
        )

        db_animes = await db.get_all_anime_posters()

        candidates = []
        if detected_info and detected_info.get("found"):
            # 2-BOSQICH: ANIQLANGAN ANIMENI BAZAMIZDAGI ANIMELAR BILAN 3 TILDA TAQQOSLASH (>= 80%)
            candidates = match_anime_in_database(detected_info, db_animes, threshold=0.80)

        # 3-BOSQICH: AGAR NOMZOD TOPILMASA, POSTER D-HASH BILAN TEKSHIRISH
        if not candidates:
            user_hash = compute_image_hash(image_data)
            user_unique_id = photo.file_unique_id
            for a in db_animes:
                a_data = a.get("data") or {}
                if isinstance(a_data, str):
                    try:
                        a_data = json.loads(a_data)
                    except Exception:
                        a_data = {}
                elif not isinstance(a_data, dict):
                    a_data = {}

                saved_unique_id = a_data.get("poster_unique_id")
                saved_hash = a_data.get("poster_hash")

                if saved_unique_id and saved_unique_id == user_unique_id:
                    candidates.append({
                        "anime": a,
                        "similarity": 100.0,
                        "raw_similarity": 1.0,
                        "matched_db_title": a.get("title", ""),
                        "matched_search_title": a.get("title", "")
                    })
                    break

                # Barcha saqlangan poster va kadrlarning hashlarini tekshirish
                saved_hashes = a_data.get("poster_hashes") or []
                if isinstance(saved_hashes, str):
                    saved_hashes = [saved_hashes]
                if saved_hash and saved_hash not in saved_hashes:
                    saved_hashes.append(saved_hash)

                best_h_sim = 0.0
                if user_hash and saved_hashes:
                    for sh in saved_hashes:
                        h_sim = hash_similarity(user_hash, sh)
                        if h_sim > best_h_sim:
                            best_h_sim = h_sim

                if best_h_sim >= 0.78:
                    candidates.append({
                        "anime": a,
                        "similarity": round(best_h_sim * 100, 1),
                        "raw_similarity": best_h_sim,
                        "matched_db_title": a.get("title", ""),
                        "matched_search_title": a.get("title", "")
                    })

            candidates.sort(key=lambda x: x["raw_similarity"], reverse=True)
            candidates = candidates[:3]

        # 4-BOSQICH: NATIJALARNI KO'RSATISH VA FOYDALANUVCHIDAN TASDIQLASH SO'ROVI
        if candidates:
            # 80% dan yuqori top 3 ta natija mavjud
            top_cand = candidates[0]
            poster = top_cand["anime"].get("poster")
            db_anime_title = top_cand["anime"].get("title", "")
            cand_data = top_cand["anime"].get("data") or {}
            if isinstance(cand_data, str):
                try:
                    cand_data = json.loads(cand_data)
                except Exception:
                    cand_data = {}
            elif not isinstance(cand_data, dict):
                cand_data = {}

            db_alts = cand_data.get("alt_titles") or []
            if isinstance(db_alts, str):
                db_alts = [db_alts]

            # Bazadagi haqiqiy rasmiy inglizcha nomni aniqlash
            db_en = ""
            for alt in db_alts:
                if isinstance(alt, str) and not has_cyrillic(alt):
                    if not re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", alt):
                        db_en = alt.strip()
                        break

            # Agar anime bazadan aniqlangan bo'lsa, bazadagi asl inglizcha nomni olamiz
            if db_en and top_cand["similarity"] >= 80.0:
                raw_en = db_en
            else:
                raw_en = (detected_info or {}).get("title_en") or db_anime_title

            raw_uz = db_anime_title if top_cand["similarity"] >= 80.0 else ((detected_info or {}).get("title_uz") or db_anime_title)
            raw_ru = (detected_info or {}).get("title_ru") or ""

            title_en, title_uz, title_ru = await ensure_multilingual_titles(
                raw_en, raw_uz, raw_ru, matched_db_title=db_anime_title
            )

            if len(candidates) == 1:
                sim_val = top_cand["similarity"]

                text = (
                    "🤖 <b>AI Rasm tahlili natijasi:</b>\n\n"
                    "🎬 <b>Aniqlangan anime:</b>\n"
                    f"🇬🇧 <b>EN:</b> {html.escape(title_en)}\n"
                    f"🇺🇿 <b>UZ:</b> {html.escape(title_uz)}\n"
                    f"🇷🇺 <b>RU:</b> {html.escape(title_ru)}\n\n"
                    f"🎯 <b>Bazamizdagi moslik:</b> <b>{html.escape(db_anime_title)}</b> ({sim_val}%)\n\n"
                    "❓ <b>Bu siz so'ragan animemi?</b>"
                )
            else:
                top_list_str = "\n".join(
                    f"{i}️⃣ <b>{html.escape(c['anime'].get('title', ''))}</b> — {c['similarity']}%"
                    for i, c in enumerate(candidates, 1)
                )
                text = (
                    "🤖 <b>AI Rasm tahlili natijasi:</b>\n\n"
                    "🎬 <b>Aniqlangan anime:</b>\n"
                    f"🇬🇧 <b>EN:</b> {html.escape(title_en)}\n"
                    f"🇺🇿 <b>UZ:</b> {html.escape(title_uz)}\n"
                    f"🇷🇺 <b>RU:</b> {html.escape(title_ru)}\n\n"
                    f"🎯 <b>Bazamizdan 80% dan yuqori mos kelgan eng yaqin animelar:</b>\n"
                    f"{top_list_str}\n\n"
                    "❓ <b>Bulardan qaysi biri siz so'ragan anime?</b>"
                )

            kb = get_ai_image_confirmation_keyboard(candidates)
            try:
                await status_msg.delete()
            except Exception:
                pass

            if poster:
                await message.answer_photo(photo=poster, caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
            return

        elif detected_info and detected_info.get("found"):
            raw_en = detected_info.get("title_en") or "Noma'lum anime"
            raw_uz = detected_info.get("title_uz") or ""
            raw_ru = detected_info.get("title_ru") or ""

            title_en, title_uz, title_ru = await ensure_multilingual_titles(
                raw_en, raw_uz, raw_ru
            )

            text = (
                "💡 <b>Rasmdan aniqlangan anime:</b>\n\n"
                f"🇬🇧 <b>EN:</b> {html.escape(title_en)}\n"
                f"🇺🇿 <b>UZ:</b> {html.escape(title_uz)}\n"
                f"🇷🇺 <b>RU:</b> {html.escape(title_ru)}\n\n"
                "ℹ️ <i>Ushbu anime hozircha bizning bot bazamizda topilmadi (o'xshashlik 80% dan past).\n"
                "Adminlar tez orada uni kanalimizga yuklashadi!</i>\n\n"
                "Boshqa anime qidirish uchun yangi rasm yuborishingiz mumkin:"
            )
            try:
                await status_msg.edit_text(text, reply_markup=get_ai_image_retry_keyboard(), parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=get_ai_image_retry_keyboard(), parse_mode="HTML")
            return

    except Exception as e:
        logger.error(f"Image search error: {e}")

    try:
        await status_msg.edit_text(
            "⚠️ <b>Kechirasiz, ushbu rasm orqali animeni aniqlab bo'lmadi.</b>\n\n"
            "<i>Iltimos, animening aniqroq kadrini (skrinshot) yuboring yoki '🏷 Anime nomi orqali' qidiruvdan foydalaning.</i>",
            reply_markup=get_ai_image_retry_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            "⚠️ <b>Kechirasiz, ushbu rasm orqali animeni aniqlab bo'lmadi.</b>\n\n"
            "<i>Iltimos, animening aniqroq kadrini (skrinshot) yuboring yoki '🏷 Anime nomi orqali' qidiruvdan foydalaning.</i>",
            reply_markup=get_ai_image_retry_keyboard(),
            parse_mode="HTML"
        )


# 6.1. ✅ AI Rasm qidiruvini tasdiqlash
@router.callback_query(F.data.startswith("ai_confirm_"))
async def handle_ai_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    anime_id = int(callback.data.replace("ai_confirm_", ""))

    anime = await db.get_anime(anime_id)
    if not anime:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "⚠️ Kechirasiz, anime topilmadi yoki o'chirilgan.",
            reply_markup=get_search_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.clear()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Foydalanuvchiga anime nomi va 1-fasl / 2-faslni tanlash oynasini chiqarish
    await show_anime_seasons_menu(callback.message, anime_id, bot, bot_username)


# 6.2. ❌ AI Rasm qidiruvini rad etish (siklni qaytadan takrorlash)
@router.callback_query(F.data == "ai_reject_search")
async def handle_ai_reject(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserSearchState.by_image)
    text = (
        "🔄 <b>Tushundim, qaytadan urinib ko'ramiz!</b>\n\n"
        "Iltimos, animening boshqa aniqroq kadrini yoki posterini yuboring:\n"
        "<i>(Surat yuborishingiz bilan AI qaytadan tahlil qiladi)</i>"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=get_search_cancel_keyboard(), parse_mode="HTML")


# 7. 📚 Barcha animelar (sahifalash bilan)
@router.callback_query(F.data.startswith("search_all_animes_"))
async def handle_search_all_animes(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.replace("search_all_animes_", ""))
    limit = 8
    offset = page * limit

    total = await db.get_animes_count()
    animes = await db.get_animes_paginated(offset=offset, limit=limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    text = f"📚 <b>Barcha animelar ro'yxati</b> (Jami: {total} ta):\n\n<i>Kerakli animeni tanlang:</i>"
    kb = get_animes_pagination_keyboard(animes, page, total_pages, prefix="search_all_animes_")
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ================= MATN ORQALI ANIME QIDIRISH (ID yoki NOM) =================

@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def handle_text_search(message: Message, bot: Bot):
    query = message.text.strip()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    # 1. Agar raqam kiritilgan bo'lsa (Anime ID)
    if query.isdigit():
        anime_id = int(query)
        await show_anime_by_id(message, anime_id, bot, bot_username)
        return

    # 2. Agar matn kiritilgan bo'lsa (Nomi bo'yicha qidiruv)
    results = await db.search_animes(query, limit=10)
    if not results:
        await message.answer(
            f"❌ <b>'{html.escape(query)}'</b> bo'yicha hech qanday anime topilmadi.\n\n"
            f"<i>Anime kodi yoki nomini to'g'ri yozganingizga ishonch hosil qiling.</i>",
            parse_mode="HTML"
        )
        return

    # Agar 1 dona anime aniq topilgan bo'lsa, to'g'ridan-to'g'ri ko'rsatish
    if len(results) == 1:
        await show_anime_seasons_menu(message, results[0]["id"], bot, bot_username)
        return

    # Bir nechta anime topilgan bo'lsa, ro'yxatini chiqarish
    text = f"🔎 <b>'{html.escape(query)}'</b> bo'yicha topilgan animelar:\n\n"
    builder = InlineKeyboardBuilder()
    for anime in results:
        text += f"▪️ <b>{html.escape(anime['title'])}</b>\n"
        text += f"   Kod: <code>{anime['id']}</code> | Tomosha: /start_{anime['id']}\n\n"
        builder.row(InlineKeyboardButton(text=f"🎬 {anime['title'][:28]}", callback_data=f"open_anime_{anime['id']}", style="primary"))

    text += "<i>Ko'rmoqchi bo'lgan animengiz ustiga bosing yoki kodini yozing.</i>"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("open_anime_"))
async def handle_open_anime_callback(callback: CallbackQuery, bot: Bot):
    anime_id = int(callback.data.replace("open_anime_", ""))
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    await callback.answer()
    await show_anime_seasons_menu(callback, anime_id, bot, bot_username)


@router.message(F.text.regexp(r"^/start_(\d+)$"))
async def handle_slash_start_anime(message: Message, bot: Bot):
    parts = message.text.split("_")
    if len(parts) > 1 and parts[1].isdigit():
        anime_id = int(parts[1])
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username
        await show_anime_by_id(message, anime_id, bot, bot_username)


# ================= MENYU VA BUYRUQLAR HANDLERLARI =================

# 1. 🗄 Kabinet
@router.message(Command("kabinet"))
@router.callback_query(F.data == "btn_cabinet")
async def handle_cabinet(event: Message | CallbackQuery):
    user_id = event.from_user.id
    user = await db.get_user(user_id)
    is_vip = await db.check_user_vip_status(user_id)

    vip_str = "❌ Faol emas"
    if is_vip and user and user.get("vip_until"):
        until_date = user["vip_until"][:10]
        vip_str = f"💎 Faol ({until_date} gacha)"

    balance = user.get("balance", 0) if user else 0
    full_name = html.escape(event.from_user.full_name)

    text = (
        f"👤 <b>Foydalanuvchi Kabineti</b>\n\n"
        f"▫️ <b>Ismingiz:</b> {full_name}\n"
        f"▫️ <b>Sizning Telegram ID:</b> <code>{user_id}</code>\n"
        f"▫️ <b>Hisobingiz:</b> {balance} so'm\n"
        f"▫️ <b>VIP Status:</b> {vip_str}\n\n"
        f"<i>VIP obuna orqali siz barcha animelarni homiy kanallarsiz, tezkor va qulay tomosha qilishingiz mumkin!</i>"
    )

    kb = get_cabinet_keyboard()

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


# 2. 💎 VIP Obuna (/vip)
@router.message(Command("vip"))
@router.callback_query(F.data == "btn_vip")
async def handle_vip_info(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "╭── ✦ <b>PREMIUM VIP OBUNA</b> ✦ ──╮\n"
        "│\n"
        "│  👑 <b>VIP afzalliklari:</b>\n"
        "│  • 🚫 Majburiy homiy kanallarsiz tomosha\n"
        "│  • ⚡️ 1080p Ultra HD premyeralar\n"
        "│  • 📖 Manga & ⚡️ Shorts'ga to'liq kirish\n"
        "│  • 🚀 Maksimal tezlikda yuklab olish\n"
        "│  • 🎖 Maxsus profil nishoni va VIP status\n"
        "│\n"
        "├── ✦ <b>TARIFLAR VA NARXLAR</b> ✦ ──┤\n"
        "│  💎 <b>1 oylik:</b> <code>15,000 so'm</code>\n"
        "│  💎 <b>3 oylik:</b> <code>50,000 so'm</code>\n"
        "│  👑 <b>Doimiy (cheksiz):</b> <code>100,000 so'm</code>\n"
        "╰────────────────────────╯\n\n"
        "<i>To'lov qilish uchun quyidagi tariflardan birini tanlang:</i>"
    )
    kb = get_vip_plans_keyboard()
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.in_(["buy_vip_1", "buy_vip_3", "buy_vip_unlimited"]))
async def handle_select_vip_plan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    plan_key = callback.data

    plans = {
        "buy_vip_1": {"name": "1 oylik VIP", "days": 30, "price": "15,000 so'm", "amount": 15000},
        "buy_vip_3": {"name": "3 oylik VIP", "days": 90, "price": "50,000 so'm", "amount": 50000},
        "buy_vip_unlimited": {"name": "Doimiy (cheksiz) VIP", "days": 3650, "price": "100,000 so'm", "amount": 100000}
    }
    selected = plans.get(plan_key)
    await state.update_data(
        plan_key=plan_key,
        plan_name=selected["name"],
        days=selected["days"],
        price=selected["price"]
    )

    from bot.tezcheck import tezcheck_client
    tezcheck_url = None
    bill_id = None

    # Agar TezCheck integratsiyasi faollashtirilgan bo'lsa
    if tezcheck_client.is_enabled:
        try:
            bill_res = await tezcheck_client.create_bill(
                amount_uzs=selected["amount"],
                title=f"VIP Obuna - {selected['name']}",
                external_reference=f"VIP-{callback.from_user.id}-{int(time.time())}"
            )
            if bill_res.get("ok"):
                tezcheck_url = bill_res.get("payment_url")
                bill_id = bill_res.get("bill_id")
                await db.create_tezcheck_payment(
                    bill_id=bill_id,
                    user_id=callback.from_user.id,
                    plan_key=plan_key,
                    days=selected["days"],
                    amount_uzs=selected["amount"],
                    payment_url=tezcheck_url,
                    data=bill_res.get("raw")
                )
        except Exception as e:
            logging.getLogger("Users").error(f"TezCheck to'lov havolasi yaratishda xatolik: {e}")

    if tezcheck_url:
        text = (
            "╭── ✦ <b>VIP ONLAYN TO'LOV</b> ✦ ──╮\n"
            "│\n"
            f"│  💎 <b>Tarif:</b> {selected['name']}\n"
            f"│  💵 <b>To'lov summasi:</b> <code>{selected['price']}</code>\n"
            f"│  ⏱ <b>Davomiyligi:</b> {selected['days']} kun\n"
            f"│  ⚡️ <b>Tezlik:</b> Cheklovlarsiz (Ultra HD)\n"
            f"│  🛡 <b>To'lov turi:</b> Avtomatik va xavfsiz\n"
            "│\n"
            "├── ✦ <b>QO'LLAB-QUVVATLANADI</b> ✦ ──┤\n"
            "│  💳 <b>Click</b> • <b>Payme</b> • <b>Uzum Bank</b>\n"
            "│  🏦 <b>Humo</b> • <b>Uzcard</b> kartalari\n"
            "╰────────────────────────╯\n\n"
            "👇 <b>To'lovni amalga oshirish:</b>\n"
            "1️⃣ <b>«💳 Click / Payme / Uzum orqali to'lash»</b> tugmasini bosing;\n"
            "2️⃣ To'lovni o'zingizga qulay ilova orqali bajaring;\n"
            "3️⃣ Botga qaytib, <b>«🔄 To'lovni tekshirish»</b> tugmasini bosing — VIP darhol faollashadi!"
        )
    else:
        text = (
            "╭── ✦ <b>VIP ONLAYN TO'LOV</b> ✦ ──╮\n"
            "│\n"
            f"│  💎 <b>Tarif:</b> {selected['name']}\n"
            f"│  💵 <b>To'lov summasi:</b> <code>{selected['price']}</code>\n"
            f"│  ⏱ <b>Davomiyligi:</b> {selected['days']} kun\n"
            "╰────────────────────────╯\n\n"
            "👨🏻‍💻 <b>To'lov uchun admin:</b> @Jahongir02_02\n\n"
            "<i>To'lov amalga oshirilgach, administratorga xabar bering.</i>"
        )

    kb = get_vip_payment_keyboard(
        plan_key,
        callback.from_user.id,
        tezcheck_url=tezcheck_url,
        bill_id=bill_id
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("check_tz_"))
async def handle_check_tezcheck_payment(callback: CallbackQuery, bot: Bot):
    bill_id = callback.data.replace("check_tz_", "")
    await callback.answer("🔄 To'lov holati tekshirilmoqda...", show_alert=False)

    from bot.tezcheck import tezcheck_client
    payment = await db.get_tezcheck_payment(bill_id)
    if not payment:
        await callback.answer("⚠️ Ushbu to'lov hisobi topilmadi.", show_alert=True)
        return

    if payment.get("status") == "paid":
        await callback.answer("✅ Ushbu to'lov allaqachon tasdiqlangan va VIP faol!", show_alert=True)
        return

    # TezCheck API orqali holatni tekshirish
    status_res = await tezcheck_client.get_bill_status(bill_id)
    if status_res.get("is_paid"):
        user_id = payment["user_id"]
        days = payment["days"]
        await db.update_tezcheck_payment_status(bill_id, "paid")
        await db.give_vip(user_id, days)

        text = (
            "╭── ✦ <b>TO'LOV TASDIQLANDI!</b> ✦ ──╮\n"
            "│\n"
            "│  👑 <b>VIP Maqomi:</b> Muvaffaqiyatli yoqildi!\n"
            f"│  💎 <b>Tarif:</b> {payment.get('plan_key', 'VIP')}\n"
            f"│  ⏱ <b>Davomiyligi:</b> {days} kun\n"
            "│  🚀 <b>Imtiyoz:</b> Barcha animelar va bo'limlar ochiq\n"
            "╰────────────────────────╯\n\n"
            "✨ <i>Barcha cheklovlar olib tashlandi, animelarni reklamasiz va yuqori sifatda tomosha qilishingiz mumkin!</i>\n\n"
            "🍿 <b>Maroqli hordiq tilaymiz!</b>"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")
    else:
        current_status = status_res.get("status", "kutilmoqda")
        await callback.answer(
            f"⏳ To'lov holati: {current_status}.\n\nAgar to'lovni endigina amalga oshirgan bo'lsangiz, bir necha soniyadan so'ng qayta bosing.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("send_receipt_"))
async def handle_start_send_receipt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(VipPaymentState.receipt)
    text = (
        "📤 <b>To'lov chekini yuborish</b>\n\n"
        "Iltimos, to'lov amalga oshirilganligini tasdiqlovchi <b>chek rasmini (skrinshot)</b> chatga yuboring:\n\n"
        "<i>(Bekor qilish uchun /start buyrug'ini yozing)</i>"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_vip", style="danger"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(VipPaymentState.receipt, F.photo)
async def process_vip_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    plan_name = data.get("plan_name", "1 oylik VIP")
    days = data.get("days", 30)
    price = data.get("price", "15,000 so'm")

    user = message.from_user
    photo_file_id = message.photo[-1].file_id

    await state.clear()

    # Foydalanuvchiga tasdiq xabari
    await message.answer(
        "✅ <b>To'lov cheki qabul qilindi!</b>\n\n"
        "Chekingiz tekshirish uchun administratorga yuborildi. "
        "To'lov tasdiqlanishi bilan VIP obunangiz avtomatik faollashtiriladi va sizga xabar beriladi! Rahmat.",
        reply_markup=get_back_home_keyboard(),
        parse_mode="HTML"
    )

    # Adminlarga yuborish
    admin_caption = (
        f"🔔 <b>YANGI VIP TO'LOV CHEKI!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {html.escape(user.full_name)}\n"
        f"▫️ <b>Username:</b> @{user.username if user.username else 'yoq'}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"💎 <b>Tanlangan tarif:</b> {plan_name}\n"
        f"💵 <b>Summa:</b> {price}\n"
        f"⏳ <b>Muddat:</b> {days} kun"
    )

    admin_kb = get_admin_vip_approval_keyboard(user.id, days)

    for admin_id in config.admins:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=admin_caption,
                reply_markup=admin_kb,
                parse_mode="HTML"
            )
        except Exception:
            pass


# 3. /top - Animelar ro'yxati
@router.message(Command("top"))
async def handle_top_animes(message: Message):
    top_list = await db.get_top_animes(limit=10)
    if not top_list:
        await message.answer("📄 Hozircha bazada animelar mavjud emas.")
        return

    text = "🔥 <b>TOP-10 Eng ko'p ko'rilgan animelar:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for i, a in enumerate(top_list, 1):
        views = a.get("views", 0)
        title = html.escape(a.get("title", ""))
        anime_id = a.get("id")
        text += f"<b>{i}.</b> {title}\n"
        text += f"   👁 {views} ko'rish | Kod: <code>{anime_id}</code>\n\n"
        builder.row(InlineKeyboardButton(text=f"{i}. 🎬 {a['title'][:25]}", callback_data=f"open_anime_{anime_id}", style="primary"))

    text += "<i>Tomosha qilish uchun animeni tanlang:</i>"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# 4. /help - Qo'llab-quvvatlash
@router.message(Command("help"))
async def handle_help(message: Message):
    text = (
        "☎️ <b>Qo'llab-quvvatlash xizmati</b>\n\n"
        "Botda biror muammo, xatolik yoki savollaringiz bo'lsa, adminimiz bilan bog'lanishingiz mumkin:\n\n"
        "👨🏻‍💻 <b>Admin:</b> @Jahongir02_02\n"
        "📢 <b>Kanalimiz:</b> @Ani_Movei_UZ"
    )
    await message.answer(text, parse_mode="HTML")


# 5. /qollanma - Botdan foydalanish
@router.message(Command("qollanma"))
async def handle_guide(message: Message):
    text = (
        "📚 <b>Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
        "1. <b>Anime kodini kiritish:</b> Telegram kanalimizda har bir post tagida anime kodi ko'rsatilgan. Masalan <code>961</code> yozsangiz bot o'sha animeni chiqarib beradi.\n"
        "2. <b>Nom bo'yicha qidiruv:</b> Botga anime nomini qisman yoki to'liq yozsangiz, bot qidirib beradi.\n"
        "3. <b>Qismlarni tomosha qilish:</b> Chiqqan menyudan 1, 2, 3... qism tugmalarini bosib videoni yuklab olishingiz mumkin.\n"
        "4. <b>Homiy kanallar:</b> Kanallarga a'zo bo'lib, obunani tasdiqlang."
    )
    await message.answer(text, parse_mode="HTML")


# 6. 📖 Manga ko'rish
@router.callback_query(F.data == "btn_manga")
async def handle_manga(callback: CallbackQuery):
    await callback.answer()
    text = (
        "📖 <b>Manga mutolaa bo'limi</b>\n\n"
        "Tez kunda botimizda eng sara o'zbekcha tarjima qilingan mangalarni ham o'qishingiz mumkin bo'ladi!\n\n"
        "Yangiliklarni kanalimizda kuzatib boring: @Ani_Movei_UZ"
    )
    await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")


# 7. ⚡️ Shorts ko'rish
@router.callback_query(F.data == "btn_shorts")
async def handle_shorts(callback: CallbackQuery):
    await callback.answer()
    text = (
        "⚡️ <b>Anime Shorts & Lavhalar</b>\n\n"
        "Eng qiziqarli anime qisqa videolari va lahzalarini bizning maxsus kanalimizda tomosha qiling:\n\n"
        "👉 https://t.me/Ani_Movei_UZ"
    )
    await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")


# 8. ⬅️ Bosh menyuga qaytish
@router.callback_query(F.data == "btn_home")
async def handle_back_home(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    is_vip = (user_id in config.admins) or await db.check_user_vip_status(user_id)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    text = get_welcome_text(callback.from_user.full_name)
    kb = get_main_menu_keyboard(bot_username, is_vip=is_vip, user_id=user_id)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.in_(["vip_required_manga", "vip_required_shorts"]))
async def handle_vip_required_notice(callback: CallbackQuery):
    await callback.answer("🔒 Ushbu bo'lim faqat VIP foydalanuvchilar uchun!", show_alert=True)
    text = (
        "👑 <b>Hurmatli foydalanuvchi!</b>\n\n"
        "📖 <b>Manga</b> va ⚡️ <b>Shorts</b> Mini App bo'limlari faqat <b>VIP obunachilarimiz</b> uchun ochiq!\n\n"
        "💎 <b>VIP obuna imtiyozlari:</b>\n"
        "• Barcha o'zbekcha tarjima mangalarni cheklovlarsiz o'qish\n"
        "• Eng sara anime shortslarni reklamasiz tomosha qilish\n"
        "• Barcha premyera animelarni birinchilardan 1080p sifatda yuklash\n"
        "• Sponsor kanallarga majburiy a'zo bo'lish talab etilmaydi\n\n"
        "<i>VIP obunani faollashtirish uchun quyidagi tugmani bosing:</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 VIP Obuna xarid qilish", callback_data="btn_vip", style="success"))
    builder.row(InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="btn_home", style="danger"))
    await callback.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")


# 9. ✅ Obunani tekshirish callback
@router.callback_query(F.data.startswith("check_sub"))
async def handle_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    target_anime_id = None
    target_manga_id = None
    target_play = None
    if callback.data.startswith("check_sub_"):
        raw_id = callback.data.replace("check_sub_", "").strip()
        if raw_id.startswith("manga_"):
            m_str = raw_id.replace("manga_", "")
            if m_str.isdigit():
                target_manga_id = int(m_str)
        elif raw_id.startswith("play_"):
            parts = raw_id.split("_")
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                target_play = (int(parts[1]), int(parts[2]))
        elif raw_id.isdigit():
            target_anime_id = int(raw_id)

    if is_subbed:
        await callback.answer("✅ Barcha kanallarga a'zo bo'lgansiz! Rahmat.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass

        # Agar foydalanuvchi anime yoki manga ko'rish uchun tekshirgan bo'lsa, darhol ochish!
        if target_play:
            await send_episode_direct(callback.message, target_play[0], target_play[1], bot, bot_username)
        elif target_manga_id:
            await show_manga_by_id(callback, target_manga_id, bot, bot_username)
        elif target_anime_id:
            await show_anime_by_id(callback, target_anime_id, bot, bot_username)
        else:
            text = get_welcome_text(callback.from_user.full_name)
            is_vip = (user_id in config.admins) or await db.check_user_vip_status(user_id)
            kb = get_main_menu_keyboard(bot_username, is_vip=is_vip, user_id=user_id)
            await callback.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        sub_param = f"manga_{target_manga_id}" if target_manga_id else (str(target_anime_id) if target_anime_id else "")
        if sub_param:
            builder = InlineKeyboardBuilder()
            for idx, ch in enumerate(unsubbed, 1):
                title = ch.get("title", f"Kanal #{idx}")
                link = ch.get("invite_link", "https://t.me")
                builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary"))
            builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{sub_param}", style="success"))
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        else:
            kb = get_subscription_keyboard(unsubbed)
            await callback.message.edit_reply_markup(reply_markup=kb)


async def show_manga_by_id(message_or_query, manga_id: int, bot: Bot, bot_username: str):
    """Manga ma'lumotlarini kanaldagi dizaynda ko'rsatish va mutolaa tugmasi berish"""
    user_id = message_or_query.from_user.id
    is_message = isinstance(message_or_query, Message)

    # 1. Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        text = (
            "⚠️ <b>Kechirasiz, manga mutolaa qilish uchun quyidagi homiy kanallarimizga obuna bo'lishingiz kerak:</b>\n\n"
            "<i>Iltimos, kanallarga a'zo bo'lib, '✅ Obunani tekshirish' tugmasini bosing!</i>"
        )
        builder = InlineKeyboardBuilder()
        for idx, ch in enumerate(unsubbed, 1):
            title = ch.get("title", f"Kanal #{idx}")
            link = ch.get("invite_link", "https://t.me")
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary"))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_manga_{manga_id}", style="success"))
        kb = builder.as_markup()

        if is_message:
            await message_or_query.answer(text=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
        return

    # 2. Manga ma'lumotlarini olish
    manga = await db.get_manga(manga_id)
    if not manga:
        not_found_text = f"❌ <b>Kechirasiz, {manga_id} ID raqamli manga topilmadi!</b>"
        if is_message:
            await message_or_query.answer(not_found_text, parse_mode="HTML")
        else:
            await message_or_query.answer(not_found_text, show_alert=True)
        return

    m_data = manga.get("data") or {}
    if isinstance(m_data, str):
        try:
            m_data = json.loads(m_data)
        except Exception:
            m_data = {}

    m_type = m_data.get("type", "Manhwa") if isinstance(m_data, dict) else "Manhwa"
    m_genre = manga.get("genre", "Jangari").title()
    status = manga.get("status", "Davom etmoqda")
    ch_count = manga.get("chapters_count", 1)

    caption = (
        f"• <b>{html.escape(manga['title'])}</b>\n"
        f"╭━━━━━━━━━━━━━━━━━━━━━\n"
        f"▸ <b>Janr :</b> {html.escape(m_genre)}\n"
        f"▸ <b>Turi :</b> {html.escape(m_type)}\n"
        f"▸ <b>Til :</b> Uzbek\n"
        f"▸ <b>Holati :</b> {html.escape(status)}\n"
        f"▸ <b>Mavjud boblar :</b> {ch_count} ta\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{html.escape(manga.get('description', ''))}\n\n"
        f"<b>Asosiy kanal:</b> {config.manga_channel_id}"
    )

    is_vip = (user_id in config.admins) or await db.check_user_vip_status(user_id)
    manga_base = config.manga_webapp_url
    sep = "&" if "?" in manga_base else "?"
    manga_url = f"{manga_base}{sep}vip=1&user_id={user_id}&manga_id={manga_id}"

    builder = InlineKeyboardBuilder()
    if is_vip:
        builder.row(
            InlineKeyboardButton(
                text="📚 Hoziroq O'qish (Mini App) 📚",
                web_app=WebAppInfo(url=manga_url),
                style="success"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="📚 Hoziroq O'qish [VIP 🔒] 📚",
                callback_data="vip_required_manga",
                style="primary"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="👑 VIP Obunani faollashtirish",
                callback_data="btn_vip",
                style="success"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home", style="danger"))

    cover = manga.get("cover")
    try:
        if is_message:
            await message_or_query.answer_photo(
                photo=cover,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            await message_or_query.message.answer_photo(
                photo=cover,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
    except Exception:
        if is_message:
            await message_or_query.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await message_or_query.message.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(Command("admin"))
async def handle_unauthorized_admin(message: Message):
    """Admin bo'lmagan foydalanuvchilar /admin yozganda"""
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "mavjud emas"
    await message.answer(
        f"⛔️ <b>Kechirasiz, siz bot administratori emassiz!</b>\n\n"
        f"🆔 <b>Sizning Telegram ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Username:</b> {username}\n\n"
        f"💡 Agar siz bot egasi bo'lsangiz, ushbu ID raqamni sozlamalarga (ADMINS ga) qo'shing yoki @Jahongir02_02 profilingizdan kiring.",
        parse_mode="HTML"
    )
