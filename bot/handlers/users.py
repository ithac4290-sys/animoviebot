import html
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
    get_subscription_keyboard,
    get_cabinet_keyboard,
    get_back_home_keyboard,
    get_vip_plans_keyboard,
    get_vip_payment_keyboard,
    get_admin_vip_approval_keyboard,
    get_search_type_keyboard,
    get_genres_keyboard,
    get_animes_pagination_keyboard,
    get_search_cancel_keyboard
)
from bot.states import VipPaymentState, UserSearchState
from bot.utils import check_user_subscriptions

router = Router()


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
        f"💡 /qollanma — Botdan foydalanish qo'llanmasi</blockquote>\n\n"
        f"🔥 <b>Botga to'g'ridan-to'g'ri anime kodi yoki nomini yozishingiz mumkin.</b>"
    )


def format_anime_caption(anime: dict, bot_username: str) -> str:
    """Anime card caption formati"""
    title = html.escape(anime.get("title", ""))
    status = html.escape(anime.get("status", "Davom etmoqda"))
    channel = html.escape(anime.get("channel", f"@{bot_username}"))
    anime_id = anime.get("id")

    return (
        f"🎬 <b>{title}</b>\n\n"
        f"<blockquote>• 📌 Holati: {status}\n"
        f"• ⚡️ Sifat: 720p, 1080p\n"
        f"• 📢 {channel}</blockquote>\n\n"
        f"🏷 <b>Botimiz:</b> @{bot_username}\n"
        f"📮 <b>Anime ID:</b> <code>{anime_id}</code>\n"
        f"📎 <b>Link:</b> https://t.me/{bot_username}?start={anime_id}"
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


# ================= ANIME KO'RISH LOGIKASI =================

async def show_anime_by_id(message_or_query, anime_id: int, bot: Bot, bot_username: str):
    """Animeni 2-rasm dizaynida ko'rsatish"""
    user_id = message_or_query.from_user.id

    # 1. Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        text = (
            "⚠️ <b>Kechirasiz, anime tomosha qilish uchun quyidagi homiy kanallarimizga obuna bo'lishingiz kerak:</b>\n\n"
            "<i>Iltimos, kanallarga a'zo bo'lib, '✅ Obunani tekshirish' tugmasini bosing!</i>"
        )
        # Obuna tekshirilgandan so'ng to'g'ridan-to'g'ri o'sha anime ochilishi uchun
        builder = InlineKeyboardBuilder()
        for idx, ch in enumerate(unsubbed, 1):
            title = ch.get("title", f"Kanal #{idx}")
            link = ch.get("invite_link", "https://t.me")
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{anime_id}"))
        kb = builder.as_markup()

        if isinstance(message_or_query, Message):
            await message_or_query.answer(text=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_or_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
        return

    # 2. Bazadan animeni olish
    anime = await db.get_anime(anime_id)
    if not anime:
        not_found_text = f"❌ <b>Kechirasiz, {anime_id} ID raqamli anime topilmadi!</b>"
        if isinstance(message_or_query, Message):
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
    if isinstance(message_or_query, Message):
        await message_or_query.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_query.message.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "episodes_coming_soon")
async def handle_episodes_coming_soon(callback: CallbackQuery):
    await callback.answer("⏳ Ushbu animening qismlari tez kunda yuklanadi!", show_alert=True)


# ================= QISM TUGMASI BOSILGANDA =================

@router.callback_query(F.data.startswith("play_"))
async def handle_play_episode(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    # Majburiy obunani tekshirish
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    if not is_subbed:
        await callback.answer("⚠️ Iltimos, oldin kanallarga a'zo bo'ling!", show_alert=True)
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

    await callback.answer(f"⏳ {ep_num}-qism yuborilmoqda...")

    # Tanlangan qism belgisini klaviaturada yangilash ([ 📀 ] - {ep_num})
    try:
        episodes = await db.get_anime_episodes(anime_id)
        uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
        updated_kb = get_anime_keyboard(anime_id, uploaded_ep_nums, page=page, current_ep=ep_num)
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
    except Exception as e:
        await callback.message.answer(f"❌ Videoni yuborishda xatolik yuz berdi: {str(e)}")


# ================= ❌ YOPISH TUGMASI =================

@router.callback_query(F.data == "close_anime_view")
async def handle_close_view(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer("Xabar o'chirildi.")


# ================= ⏩ QISMLARNI SAHIFALASH (PAGINATION) =================

@router.callback_query(F.data.startswith("ep_page_"))
async def handle_episodes_page(callback: CallbackQuery):
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
        await show_anime_by_id(message, results[0]["id"], bot, bot_username)
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
        builder.row(InlineKeyboardButton(text=f"{badge} {a['title'][:25]}", callback_data=f"open_anime_{a['id']}"))

    builder.row(
        InlineKeyboardButton(text="⬅️ Qidiruv menyusi", callback_data="btn_search_menu"),
        InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="btn_home")
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
    status_msg = await message.answer("🔍 <b>Rasm tahlil qilinmoqda, iltimos kuting...</b>", parse_mode="HTML")

    photo = message.photo[-1]

    try:
        from io import BytesIO
        import aiohttp
        from bot.image_search import compute_image_hash, hash_similarity

        photo_bytes_io = BytesIO()
        await bot.download(photo, destination=photo_bytes_io)
        image_data = photo_bytes_io.getvalue()

        # 1-BOSQICH: BAZAMIZDAGI ANIMELARNING POSTERLARI BILAN SOLISHTIRISH (Perceptual Hash qidiruv)
        user_hash = compute_image_hash(image_data)
        user_unique_id = photo.file_unique_id

        local_animes = await db.get_all_anime_posters()
        best_match = None
        best_sim = 0.0

        for a in local_animes:
            a_data = a.get("data") or {}
            saved_unique_id = a_data.get("poster_unique_id")
            saved_hash = a_data.get("poster_hash")

            # Agar anime poster hashi hali hisoblanmagan bo'lsa, avtomatik hisoblab bazaga saqlash
            if not saved_hash and a.get("poster"):
                try:
                    p_file = await bot.get_file(a["poster"])
                    p_bio = BytesIO()
                    await bot.download_file(p_file.file_path, destination=p_bio)
                    saved_hash = compute_image_hash(p_bio.getvalue())
                    saved_unique_id = p_file.file_unique_id
                    await db.update_anime_poster_hash(a["id"], saved_hash, saved_unique_id)
                except Exception:
                    pass

            if saved_unique_id and saved_unique_id == user_unique_id:
                best_match = a
                best_sim = 1.0
                break

            if saved_hash and user_hash:
                sim = hash_similarity(user_hash, saved_hash)
                if sim > best_sim:
                    best_sim = sim
                    if sim >= 0.78:
                        best_match = a

        # Agar bazamizdagi animelardan biri bilan o'xshashlik >= 78% bo'lsa
        if best_match and best_sim >= 0.78:
            anime_id = best_match["id"]
            await db.increment_anime_views(anime_id)
            bot_info = await bot.get_me()
            bot_username = bot_info.username or config.bot_username
            caption = format_anime_caption(best_match, bot_username)
            episodes = await db.get_anime_episodes(anime_id)
            uploaded_ep_nums = [ep["episode_num"] for ep in episodes]
            kb = get_anime_keyboard(anime_id, uploaded_ep_nums)

            sim_percent = round(best_sim * 100, 1)
            try:
                await status_msg.delete()
            except Exception:
                pass

            poster = best_match.get("poster")
            if poster:
                await message.answer_photo(
                    photo=poster,
                    caption=f"🎯 <b>Rasm orqali bazamizdan aniqlandi ({sim_percent}%):</b>\n\n{caption}",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"🎯 <b>Rasm orqali bazamizdan aniqlandi ({sim_percent}%):</b>\n\n{caption}",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            return

        # 2-BOSQICH: TRACE.MOE ORQALI GLOBAL QIDIRUV (Epizod kadrlarini aniqlash)
        headers = {
            "Content-Type": "image/jpeg"
        }
        if config.trace_moe_api_key:
            headers["x-trace-secret"] = config.trace_moe_api_key

        async with aiohttp.ClientSession() as session:
            trace_url = "https://api.trace.moe/search?cutBorders&anilistInfo"
            async with session.post(trace_url, data=image_data, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("result", [])
                    if results:
                        best = results[0]
                        similarity = best.get("similarity", 0)
                        if similarity >= 0.68:
                            anilist = best.get("anilist") or {}
                            title_info = anilist.get("title") or {}
                            romaji_title = title_info.get("romaji") or ""
                            english_title = title_info.get("english") or ""
                            native_title = title_info.get("native") or ""

                            filename = best.get("filename", "")
                            clean_filename = filename.split("]")[-1].split("[")[0].strip() if "]" in filename else filename
                            clean_filename = clean_filename.split("-")[0].strip()

                            episode_num = best.get("episode")
                            similarity_percent = round(similarity * 100, 1)

                            display_title = english_title or romaji_title or clean_filename

                            candidate_queries = []
                            for candidate in [romaji_title, english_title, clean_filename]:
                                if candidate and candidate not in candidate_queries:
                                    candidate_queries.append(candidate)
                                    words = candidate.split()
                                    if len(words) > 1 and words[0] not in candidate_queries:
                                        candidate_queries.append(words[0])

                            db_results = []
                            for q in candidate_queries:
                                found = await db.search_animes(q, limit=5)
                                if found:
                                    db_results = found
                                    break

                            ep_str = f"\n📌 <b>Taxminiy qism:</b> {episode_num}-qism" if episode_num else ""

                            if db_results:
                                await status_msg.edit_text(
                                    f"✅ <b>Anime aniqlandi:</b> {html.escape(display_title)}\n"
                                    f"🎯 <b>Aniqlik darajasi:</b> {similarity_percent}%{ep_str}\n\n"
                                    f"🎬 <b>Bazamizdan topilgan natijalar:</b>",
                                    reply_markup=get_animes_pagination_keyboard(db_results, 0, 1),
                                    parse_mode="HTML"
                                )
                                return
                            else:
                                await status_msg.edit_text(
                                    f"💡 <b>Rasmdan aniqlangan anime:</b>\n"
                                    f"🎬 <b>Nomi:</b> <i>{html.escape(display_title)}</i>\n"
                                    f"🎯 <b>Aniqlik darajasi:</b> {similarity_percent}%{ep_str}\n\n"
                                    f"ℹ️ <i>Ushbu anime hozircha bizning bot bazamizga yuklanmagan.\n"
                                    f"Adminlar tez orada uni kanalimizga joylashadi!</i>",
                                    reply_markup=get_search_cancel_keyboard(),
                                    parse_mode="HTML"
                                )
                                return
                elif resp.status == 429:
                    await status_msg.edit_text(
                        "⚠️ <b>Juda ko'p so'rov yuborildi.</b> Iltimos, biroz kutib qaytadan urinib ko'ring.",
                        reply_markup=get_search_cancel_keyboard(),
                        parse_mode="HTML"
                    )
                    return
    except Exception:
        pass

    await status_msg.edit_text(
        "⚠️ <b>Kechirasiz, ushbu rasm orqali animeni aniqlab bo'lmadi.</b>\n\n"
        "<i>Iltimos, animening aniqroq kadrini (skrinshot) yuboring yoki '🏷 Anime nomi orqali' qidiruvdan foydalaning.</i>",
        reply_markup=get_search_cancel_keyboard(),
        parse_mode="HTML"
    )


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
        await show_anime_by_id(message, results[0]["id"], bot, bot_username)
        return

    # Bir nechta anime topilgan bo'lsa, ro'yxatini chiqarish
    text = f"🔎 <b>'{html.escape(query)}'</b> bo'yicha topilgan animelar:\n\n"
    builder = InlineKeyboardBuilder()
    for anime in results:
        text += f"▪️ <b>{html.escape(anime['title'])}</b>\n"
        text += f"   Kod: <code>{anime['id']}</code> | Tomosha: /start_{anime['id']}\n\n"
        builder.row(InlineKeyboardButton(text=f"🎬 {anime['title'][:28]}", callback_data=f"open_anime_{anime['id']}"))

    text += "<i>Ko'rmoqchi bo'lgan animengiz ustiga bosing yoki kodini yozing.</i>"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("open_anime_"))
async def handle_open_anime_callback(callback: CallbackQuery, bot: Bot):
    anime_id = int(callback.data.replace("open_anime_", ""))
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    await callback.answer()
    await show_anime_by_id(callback, anime_id, bot, bot_username)


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
        "💎 <b>VIP OBUNA BO'LIMI</b>\n\n"
        "VIP a'zolik sizga qanday afzalliklarni beradi?\n"
        "• 🚫 Barcha majburiy obuna va homiy kanallarsiz tomosha qilish\n"
        "• ⚡️ Animelarni yuqori tezlikda yuklab olish\n"
        "• 🍿 Yangi qismlarni birinchilardan bo'lib ko'rish\n"
        "• 🎖 Maxsus VIP nishoni va maqomi\n\n"
        "💵 <b>VIP Obuna narxlari:</b>\n"
        "• 1 oylik: 15,000 so'm\n"
        "• 3 oylik: 50,000 so'm\n"
        "• Doimiy (cheksiz): 100,000 so'm\n\n"
        "<i>Sotib olish uchun quyidagi tariflardan birini tanlang:</i>"
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
        "buy_vip_1": {"name": "1 oylik VIP", "days": 30, "price": "15,000 so'm"},
        "buy_vip_3": {"name": "3 oylik VIP", "days": 90, "price": "50,000 so'm"},
        "buy_vip_unlimited": {"name": "Doimiy (cheksiz) VIP", "days": 3650, "price": "100,000 so'm"}
    }
    selected = plans.get(plan_key)
    await state.update_data(
        plan_key=plan_key,
        plan_name=selected["name"],
        days=selected["days"],
        price=selected["price"]
    )

    text = (
        f"💎 <b>Tanlangan tarif:</b> {selected['name']}\n"
        f"💵 <b>To'lov summasi:</b> {selected['price']}\n\n"
        f"💳 <b>To'lov uchun karta / rekvizitlar:</b>\n"
        f"Hozirda to'lovni adminimiz orqali amalga oshirishingiz mumkin:\n\n"
        f"👨🏻‍💻 <b>Admin:</b> @Jahongir02_02\n\n"
        f"<i>To'lov chekini (skrinshotini) to'g'ridan-to'g'ri botga yuborish uchun quyidagi <b>'📤 Chek yuborish'</b> tugmasini bosing:</i>"
    )

    kb = get_vip_payment_keyboard(plan_key, callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


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
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_vip"))
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
        builder.row(InlineKeyboardButton(text=f"{i}. 🎬 {a['title'][:25]}", callback_data=f"open_anime_{anime_id}"))

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
    builder.row(InlineKeyboardButton(text="💎 VIP Obuna xarid qilish", callback_data="btn_vip"))
    builder.row(InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="btn_home"))
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
    if callback.data.startswith("check_sub_"):
        raw_id = callback.data.replace("check_sub_", "").strip()
        if raw_id.startswith("manga_"):
            m_str = raw_id.replace("manga_", "")
            if m_str.isdigit():
                target_manga_id = int(m_str)
        elif raw_id.isdigit():
            target_anime_id = int(raw_id)

    if is_subbed:
        await callback.answer("✅ Barcha kanallarga a'zo bo'lgansiz! Rahmat.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass

        # Agar foydalanuvchi anime yoki manga ko'rish uchun tekshirgan bo'lsa, darhol ochish!
        if target_manga_id:
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
                builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link))
            builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{sub_param}"))
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
            builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link))
        builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_manga_{manga_id}"))
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
                web_app=WebAppInfo(url=manga_url)
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="📚 Hoziroq O'qish [VIP 🔒] 📚",
                callback_data="vip_required_manga"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="👑 VIP Obunani faollashtirish",
                callback_data="btn_vip"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home"))

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
