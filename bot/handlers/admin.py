import html
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import db
from bot.filters import IsAdminFilter
from bot.states import (
    AddAnimeState,
    AddEpisodeState,
    AddChannelState,
    GiveVipState,
    BroadcastState,
    DeleteAnimeState,
    AddMangaState,
    AddShortsState,
    AddChapterState,
    DeleteMangaState
)
from bot.keyboards import (
    get_admin_main_keyboard,
    get_admin_cancel_keyboard,
    get_status_keyboard,
    get_channel_post_keyboard,
    get_delete_confirm_keyboard,
    get_admin_channel_select_keyboard,
    get_admin_recent_animes_keyboard,
    get_admin_after_episode_keyboard,
    get_animes_list_keyboard,
    get_anime_manage_keyboard,
    get_admin_recent_mangas_keyboard,
    get_admin_finish_chapter_keyboard,
    get_admin_after_chapter_keyboard,
    get_admin_delete_manga_keyboard,
    get_confirm_delete_manga_keyboard
)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


# ================= /admin BUYRUG'I VA ASOSIY MENYU =================

@router.message(Command("admin"))
async def handle_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "👑 <b>Admin boshqaruv paneliga xush kelibsiz!</b>\n\n"
        "Quyidagi menyu orqali botni to'liq boshqarishingiz mumkin:"
    )
    await message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_home")
async def handle_admin_home_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = (
        "👑 <b>Admin boshqaruv paneli</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_cancel")
async def handle_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Amal bekor qilindi.")
    text = "👑 <b>Admin paneli:</b>"
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


# ================= 1. YANGI ANIME QO'SHISH VA KANALGA POST JOYLASH (1-rasm dizayni) =================

@router.callback_query(F.data == "admin_add_anime")
async def start_add_anime(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddAnimeState.title)
    text = (
        "🎬 <b>Yangi anime qo'shish</b>\n\n"
        "1-qadam: Anime nomini yozing:\n"
        "<i>(Masalan: Salom, men jodugarman. sevgilim sevgi eliksirini tayyorlashimni so'radi)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddAnimeState.title)
async def process_anime_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddAnimeState.poster)
    await message.answer(
        "2-qadam: Anime posterini (rasmini) yuboring:",
        reply_markup=get_admin_cancel_keyboard()
    )


@router.message(AddAnimeState.poster, F.photo | F.document)
async def process_anime_poster(message: Message, state: FSMContext, bot: Bot):
    photo_file_id = None
    photo_unique_id = None
    poster_hash = None

    if message.photo:
        photo_obj = message.photo[-1]
        photo_file_id = photo_obj.file_id
        photo_unique_id = photo_obj.file_unique_id
    elif message.document:
        photo_file_id = message.document.file_id
        photo_unique_id = message.document.file_unique_id
    else:
        await message.answer("⚠️ Iltimos, anime posterini (rasm yoki fayl ko'rinishida) yuboring:")
        return

    try:
        from io import BytesIO
        from bot.image_search import compute_image_hash
        target = message.photo[-1] if message.photo else message.document
        bio = BytesIO()
        await bot.download(target, destination=bio)
        poster_hash = compute_image_hash(bio.getvalue())
    except Exception:
        pass

    await state.update_data(
        poster=photo_file_id,
        poster_unique_id=photo_unique_id,
        poster_hash=poster_hash
    )
    await state.set_state(AddAnimeState.status)
    await message.answer(
        "3-qadam: Anime holatini tanlang yoki yozing:",
        reply_markup=get_status_keyboard()
    )


@router.message(AddAnimeState.poster)
async def process_anime_poster_invalid(message: Message):
    await message.answer(
        "⚠️ Iltimos, anime posterini rasm yoki fotosurat ko'rinishida yuboring:",
        reply_markup=get_admin_cancel_keyboard()
    )


@router.callback_query(AddAnimeState.status, F.data.in_(["status_davom", "status_tugallangan"]))
async def process_anime_status_cb(callback: CallbackQuery, state: FSMContext):
    status_text = "Davom etmoqda" if callback.data == "status_davom" else "Tugallangan"
    await state.update_data(status=status_text)
    await callback.answer()
    await state.set_state(AddAnimeState.episodes_count)
    await callback.message.answer(
        "4-qadam: Qismlar sonini yozing:\n<i>(Masalan: 6 qism yoki 12)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAnimeState.status)
async def process_anime_status_text(message: Message, state: FSMContext):
    await state.update_data(status=message.text.strip())
    await state.set_state(AddAnimeState.episodes_count)
    await message.answer(
        "4-qadam: Qismlar sonini yozing:\n<i>(Masalan: 6 qism yoki 12)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAnimeState.episodes_count)
async def process_anime_episodes(message: Message, state: FSMContext):
    episodes_count = message.text.strip()
    if not any(char.isdigit() for char in episodes_count):
        episodes_count += " qism"
    elif "qism" not in episodes_count.lower():
        episodes_count += " qism"

    await state.update_data(episodes_count=episodes_count)
    await state.set_state(AddAnimeState.genres)
    await message.answer(
        "5-qadam: Janrlarini yozing:\n<i>(Masalan: Fantastika Romantika)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAnimeState.genres)
async def process_anime_genres(message: Message, state: FSMContext):
    await state.update_data(genres=message.text.strip())
    await state.set_state(AddAnimeState.channel)
    default_ch = config.default_channel_id or "@Ani_Movei_UZ"
    await message.answer(
        f"6-qadam: Asosiy kanalni tanlang yoki boshqa kanal username'ini yozing:\n"
        f"<i>(Standart: {default_ch})</i>",
        reply_markup=get_admin_channel_select_keyboard(default_ch),
        parse_mode="HTML"
    )


def format_channel_target(raw: str) -> str:
    """Kanal havolasi yoki nomini Telegram chat_id formatiga tozalash"""
    raw = raw.strip()
    raw = raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "").strip("/")
    if raw.startswith("-100") or (raw.startswith("-") and raw[1:].isdigit()):
        return raw
    if not raw.startswith("@"):
        raw = f"@{raw}"
    return raw


async def _finalize_anime_creation(target_channel: str, reply_event: Message, state: FSMContext, bot: Bot):
    """Animeni DB ga saqlash va kanalga postlash jarayoni"""
    clean_target = format_channel_target(target_channel)
    data = await state.get_data()
    title = data["title"]
    poster = data["poster"]
    status = data["status"]
    episodes_count = data["episodes_count"]
    genres = data["genres"]

    # 1. Bazaga yangi animeni saqlash
    anime_id = await db.add_anime(
        title=title,
        poster=poster,
        status=status,
        episodes_count=episodes_count,
        genres=genres,
        channel=clean_target,
        poster_hash=data.get("poster_hash"),
        poster_unique_id=data.get("poster_unique_id")
    )

    await state.clear()

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    # 2. Kanal postini tayyorlash
    clean_title = title.replace(r"\'", "'")
    channel_post_caption = (
        f"{html.escape(clean_title)}\n\n"
        f"<blockquote>├• Holati: {html.escape(status)}\n"
        f"├• Anime: {html.escape(episodes_count)}\n"
        f"├• Janrlari: {html.escape(genres)}\n"
        f"├• Kanal: {html.escape(clean_target)}</blockquote>"
    )

    channel_kb = get_channel_post_keyboard(bot_username, anime_id)

    # 3. Kanalga avtomatik post yuborish
    post_channel_target = clean_target
    posted_to_channel = False
    error_msg = ""

    try:
        await bot.send_photo(
            chat_id=post_channel_target,
            photo=poster,
            caption=channel_post_caption,
            reply_markup=channel_kb,
            parse_mode="HTML"
        )
        posted_to_channel = True
    except Exception as e:
        error_msg = str(e)
        if config.default_channel_id and config.default_channel_id != post_channel_target:
            try:
                await bot.send_photo(
                    chat_id=config.default_channel_id,
                    photo=poster,
                    caption=channel_post_caption,
                    reply_markup=channel_kb,
                    parse_mode="HTML"
                )
                posted_to_channel = True
                post_channel_target = config.default_channel_id
            except Exception as e2:
                error_msg = f"{error_msg} | Zaxira kanal: {e2}"

    # 4. Adminga hisobot berish
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    success_text = (
        f"✅ <b>Yangi anime muvaffaqiyatli saqlandi!</b>\n\n"
        f"🆔 <b>Anime ID:</b> <code>{anime_id}</code>\n"
        f"📌 <b>Nomi:</b> {html.escape(title)}\n"
        f"📎 <b>Bot havolasi:</b> https://t.me/{bot_username}?start={anime_id}\n\n"
    )

    builder.row(
        InlineKeyboardButton(
            text="🎬 1-qismni yuklash",
            callback_data=f"quick_add_ep_{anime_id}_1",
            style="success"
        )
    )

    if posted_to_channel:
        success_text += f"📢 <b>{post_channel_target} kanaliga post muvaffaqiyatli joylandi!</b>"
        builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="primary"))
    else:
        cause_tip = ""
        lowered = error_msg.lower()
        if "chat not found" in lowered:
            cause_tip = "\n💡 <i>Tavsiya: Kanal topilmadi. Kanal username to'g'riligini va kanal ommaviy (public) ekanligini tekshiring.</i>"
        elif "not a member" in lowered or "administrator" in lowered or "not enough rights" in lowered or "restricted" in lowered:
            cause_tip = f"\n💡 <i>Tavsiya: Bot (@{bot_username}) ushbu kanalda <b>administrator</b> qilinmagan! Botni kanalingizga admin qilib qo'shing va xabar yozish ruxsatini bering.</i>"

        success_text += (
            f"⚠️ <b>Kanalga post joylanmadi!</b>\n"
            f"Kanal: <code>{post_channel_target}</code>\n"
            f"Xatolik: <code>{html.escape(error_msg)}</code>"
            f"{cause_tip}\n\n"
            f"<i>Botni kanalga admin qilib qo'shgach, quyidagi tugma orqali qayta urinib ko'rishingiz mumkin:</i>"
        )
        builder.row(InlineKeyboardButton(text="🔄 Qayta kanalga postlash", callback_data=f"repost_{anime_id}", style="primary"))
        builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="danger"))

    await reply_event.answer(success_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(AddAnimeState.channel, F.data == "use_default_channel")
async def process_anime_channel_default_cb(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    default_ch = config.default_channel_id or "@Ani_Movei_UZ"
    await _finalize_anime_creation(target_channel=default_ch, reply_event=callback.message, state=state, bot=bot)


@router.message(AddAnimeState.channel)
async def process_anime_channel_finish(message: Message, state: FSMContext, bot: Bot):
    target_channel = message.text.strip()
    await _finalize_anime_creation(target_channel=target_channel, reply_event=message, state=state, bot=bot)


@router.callback_query(F.data.startswith("repost_"))
async def handle_repost_to_channel(callback: CallbackQuery, bot: Bot):
    anime_id = int(callback.data.replace("repost_", ""))
    anime = await db.get_anime(anime_id)
    if not anime:
        await callback.answer("Anime topilmadi!", show_alert=True)
        return

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    title = anime["title"]
    poster = anime["poster"]
    status = anime.get("status", "Davom etmoqda")
    episodes_count = anime.get("episodes_count", "12")
    channel = format_channel_target(anime.get("channel", config.default_channel_id))

    channel_post_caption = (
        f"{html.escape(title.replace(r'''\' ''', ''' ' '''))}\n\n"
        f"<blockquote>├• Holati: {html.escape(status)}\n"
        f"├• Anime: {html.escape(episodes_count)}\n"
        f"├• Janrlari: {html.escape(anime.get('genres', ''))}\n"
        f"├• Kanal: {html.escape(channel)}</blockquote>"
    )
    channel_kb = get_channel_post_keyboard(bot_username, anime_id)

    try:
        await bot.send_photo(
            chat_id=channel,
            photo=poster,
            caption=channel_post_caption,
            reply_markup=channel_kb,
            parse_mode="HTML"
        )
        await callback.answer("✅ Kanalga muvaffaqiyatli joylandi!", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>{html.escape(title)}</b> animesi <b>{channel}</b> kanaliga muvaffaqiyatli joylandi!",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {str(e)[:100]}", show_alert=True)


# ================= 2. QISM YUKLASH (BIR NECHTA VIDEOLARNI AVTO ANIQLASH) =================

def extract_episode_number(caption: Optional[str] = None, filename: Optional[str] = None) -> Optional[int]:
    """
    Video sarlavhasi (caption) yoki fayl nomidan qism raqamini avtomatik aniqlash.
    Qo'llab-quvvatlanadigan formatlar:
    - 1-qism, 2 qism, Qism: 3
    - 1-seriya, 2 seriya, Seriya 3
    - Episode 5, Ep. 6, EP07
    - S01E08, E09
    - Fayl nomi: Naruto - 10.mp4, Black_Clover_11_[1080p].mkv, 12.mp4
    - Yolg'iz raqam: 13
    """
    patterns = [
        r'(?i)(\d+)\s*[-_]?\s*qism',
        r'(?i)qism\s*[-_:#]?\s*(\d+)',
        r'(?i)(\d+)\s*[-_]?\s*seriya',
        r'(?i)seriya\s*[-_:#]?\s*(\d+)',
        r'(?i)\bep(?:isode)?\.?\s*[-_:#]?\s*(\d+)',
        r'(?i)\bs\d+e(\d+)',
        r'(?i)\be(\d{1,4})\b'
    ]
    for p in patterns:
        if caption:
            m = re.search(p, caption)
            if m:
                return int(m.group(1))
        if filename:
            m = re.search(p, filename)
            if m:
                return int(m.group(1))

    # Fayl nomi yoki matndan qism raqamini ajratish
    for source in [caption, filename]:
        if not source:
            continue
        clean = re.sub(r'(?i)\b(1080p|720p|480p|360p|2160p|4k|x264|x265|hevc|aac)\b', '', source)
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', clean)
        clean = clean.replace('_', ' ').replace('-', ' ')
        nums = re.findall(r'\b(\d{1,4})\b', clean)
        valid_nums = [int(n) for n in nums if not (1950 <= int(n) <= 2030)]
        if valid_nums:
            return valid_nums[-1]

    return None


async def _setup_episode_upload(anime_id: int, reply_target: Any, state: FSMContext):
    """Anime qismini yuklash uchun qadamni tayyorlash"""
    anime = await db.get_anime(anime_id)
    if not anime:
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer("❌ Anime topilmadi!", show_alert=True)
        else:
            await reply_target.answer("❌ Anime topilmadi!")
        return

    episodes = await db.get_anime_episodes(anime_id)
    existing_nums = [e["episode_num"] for e in episodes]
    next_ep = max(existing_nums, default=0) + 1
    nums_str = ", ".join(str(n) for n in sorted(existing_nums)) if existing_nums else "Hozircha qismlar yo'q"

    await state.update_data(
        anime_id=anime_id,
        anime_title=anime["title"],
        next_ep=next_ep,
        manual_ep_num=None,
        uploaded_in_session=[]
    )
    # Admin darhol videolarni tashlashi mumkin bo'lishi uchun video holatiga o'tkazamiz
    await state.set_state(AddEpisodeState.video)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"▶️ Tavsiya etilgan: {next_ep}-qism",
            callback_data=f"set_ep_num_{anime_id}_{next_ep}",
            style="success"
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))

    text = (
        f"🎬 Tanlangan anime: <b>{html.escape(anime['title'])}</b>\n\n"
        f"📁 <b>Yuklangan qismlar ({len(existing_nums)} ta):</b> {nums_str}\n"
        f"💡 <b>Tavsiya etilgan navbatdagi qism:</b> {next_ep}\n\n"
        f"📹 <b>Videolarni yuboring (bitta yoki birdaniga ko'plab tashlashingiz mumkin):</b>\n"
        f"• Bot video matni (caption) yoki fayl nomidan qismni o'zi avtomatik aniqlaydi (masalan: <i>1-qism, Episode 2, 03.mp4</i>).\n"
        f"• Agar matnda raqam bo'lmasa, navbatdagi <b>{next_ep}-qismdan</b> boshlab ketma-ket joylaydi.\n\n"
        f"<i>Yoki aniq bitta qismga yuklash uchun qism raqamini yozing yoki tavsiya tugmasini bosing:</i>"
    )

    if isinstance(reply_target, CallbackQuery):
        await reply_target.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    elif isinstance(reply_target, Message):
        await reply_target.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "admin_add_episode")
async def start_add_episode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddEpisodeState.anime_id)

    recent = await db.get_animes_paginated(offset=0, limit=6)
    text = (
        "🎬 <b>Anime qismini yuklash bo'limi</b>\n\n"
        "Quyidagi ro'yxatdan kerakli animeni tanlang yoki uning <b>ID raqamini</b> yozing:\n"
    )
    if recent:
        text += "\n📌 <i>Oxirgi qo'shilgan animelar:</i>\n"
        for a in recent:
            text += f"• ID: <code>{a['id']}</code> — <b>{html.escape(a['title'][:28])}</b> (Yuklangan: {a.get('uploaded_episodes', 0)} ta)\n"
        kb = get_admin_recent_animes_keyboard(recent, action_prefix="admin_pick_anime_")
    else:
        text += "\n<i>Hozircha botda animelar yo'q. Avval 'Yangi anime qo'shish' orqali anime yarating.</i>"
        kb = get_admin_cancel_keyboard()

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_pick_anime_"))
async def handle_pick_anime_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    anime_id = int(callback.data.replace("admin_pick_anime_", ""))
    await _setup_episode_upload(anime_id, callback, state)


@router.callback_query(F.data.startswith("set_ep_num_"))
async def handle_set_ep_num_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    anime_id = int(parts[3])
    ep_num = int(parts[4])

    anime = await db.get_anime(anime_id)
    anime_title = anime["title"] if anime else "Anime"

    await state.update_data(
        anime_id=anime_id,
        episode_num=ep_num,
        manual_ep_num=ep_num,
        next_ep=ep_num,
        anime_title=anime_title
    )
    await state.set_state(AddEpisodeState.video)

    await callback.message.edit_text(
        f"🎬 <b>{html.escape(anime_title)}</b>\n\n"
        f"➡️ <b>{ep_num}-qism</b> videosini yuboring (yoki birdaniga bir nechta videolarni tashlang):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("quick_add_ep_"))
async def handle_quick_add_ep_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    anime_id = int(parts[3])
    ep_num = int(parts[4])

    anime = await db.get_anime(anime_id)
    if not anime:
        await callback.answer("Anime topilmadi!", show_alert=True)
        return

    await state.update_data(
        anime_id=anime_id,
        episode_num=ep_num,
        manual_ep_num=ep_num,
        next_ep=ep_num,
        anime_title=anime["title"],
        uploaded_in_session=[]
    )
    await state.set_state(AddEpisodeState.video)

    text = (
        f"🎬 <b>{html.escape(anime['title'])}</b>\n\n"
        f"➡️ <b>{ep_num}-qism</b> videosini yuboring (yoki birdaniga bir nechta videolarni tashlang):"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddEpisodeState.anime_id)
async def process_episode_anime_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Anime ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan kiriting:")
        return

    anime_id = int(message.text)
    anime = await db.get_anime(anime_id)
    if not anime:
        await message.answer(f"❌ {anime_id} ID raqamli anime topilmadi. Qaytadan kiriting:")
        return

    await _setup_episode_upload(anime_id, message, state)


@router.message(AddEpisodeState.episode_num)
async def process_episode_num(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Qism raqami faqat butun son bo'lishi kerak. Masalan: 1")
        return

    ep_num = int(message.text)
    data = await state.get_data()
    anime_title = data.get("anime_title", "Anime")

    await state.update_data(episode_num=ep_num, manual_ep_num=ep_num, next_ep=ep_num)
    await state.set_state(AddEpisodeState.video)
    await message.answer(
        f"🎬 <b>{html.escape(anime_title)}</b>\n\n"
        f"➡️ <b>{ep_num}-qism</b> videosini yuboring (yoki birdaniga bir nechta videolarni tashlang):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddEpisodeState.video, F.video | F.document)
@router.message(AddEpisodeState.episode_num, F.video | F.document)
async def process_episode_file(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = data.get("anime_id")
    anime_title = data.get("anime_title", "Anime")
    manual_ep_num = data.get("manual_ep_num")

    if not anime_id:
        await message.answer("⚠️ Avval animeni tanlang!")
        return

    # Sarlavha yoki fayl nomidan qism raqamini avtomatik aniqlash
    filename = message.document.file_name if message.document else None
    detected_ep = extract_episode_number(message.caption, filename)

    if manual_ep_num is not None:
        ep_num = manual_ep_num
        await state.update_data(manual_ep_num=None)
    elif detected_ep is not None:
        ep_num = detected_ep
    else:
        next_ep = data.get("next_ep")
        if not next_ep:
            episodes = await db.get_anime_episodes(anime_id)
            existing_nums = [e["episode_num"] for e in episodes]
            next_ep = max(existing_nums, default=0) + 1
        ep_num = next_ep

    # Keyingi videolar uchun navbatdagi qism raqamini yangilaymiz
    await state.update_data(next_ep=ep_num + 1)

    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    else:
        file_id = message.document.file_id
        file_type = "document"

    await db.add_episode(
        anime_id=anime_id,
        episode_num=ep_num,
        file_id=file_id,
        file_type=file_type,
        caption=message.caption
    )

    uploaded_in_session = data.get("uploaded_in_session", [])
    if ep_num not in uploaded_in_session:
        uploaded_in_session.append(ep_num)
    await state.update_data(uploaded_in_session=uploaded_in_session)
    await state.set_state(AddEpisodeState.video)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Yakunlash ({len(uploaded_in_session)} ta yuklandi)",
            callback_data=f"finish_upload_episodes_{anime_id}",
            style="success"
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))

    await message.reply(
        f"✅ <b>{html.escape(anime_title)}</b>: <b>{ep_num}-qism</b> muvaffaqiyatli saqlandi!\n\n"
        f"<i>Yana videolarni tashlashingiz mumkin yoki tugatgach '✅ Yakunlash' tugmasini bosing.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


async def _finish_episodes_upload(target: Any, state: FSMContext, anime_id: int, anime_title: str):
    data = await state.get_data()
    uploaded = data.get("uploaded_in_session", [])
    await state.clear()

    nums_str = ", ".join(str(n) for n in sorted(set(uploaded))) if uploaded else "0"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎬 Animeni ko'rish", callback_data=f"admin_view_anime_{anime_id}", style="primary"),
        InlineKeyboardButton(text="➕ Yana qism yuklash", callback_data=f"admin_pick_anime_{anime_id}", style="success")
    )
    builder.row(InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel", style="primary"))

    msg_text = (
        f"🎉 <b>{html.escape(anime_title)}</b> animesiga "
        f"<b>{len(uploaded)} ta qism</b> ({nums_str}) muvaffaqiyatli saqlandi!\n\n"
        f"Kerakli bo'limni tanlang:"
    )

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(msg_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await target.message.answer(msg_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    elif isinstance(target, Message):
        await target.answer(msg_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("finish_upload_episodes_"))
async def handle_finish_upload_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    anime_id = int(parts[3])
    anime = await db.get_anime(anime_id)
    data = await state.get_data()
    anime_title = anime["title"] if anime else data.get("anime_title", "Anime")
    await _finish_episodes_upload(callback, state, anime_id, anime_title)


@router.message(AddEpisodeState.video, F.text)
async def process_episode_text(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    data = await state.get_data()
    anime_id = data.get("anime_id")
    anime_title = data.get("anime_title", "Anime")

    if text in ["/done", "done", "tayyor", "yakunlash", "tugadi", "tamom"]:
        await _finish_episodes_upload(message, state, anime_id, anime_title)
        return

    if message.text.strip().isdigit():
        ep_num = int(message.text.strip())
        await state.update_data(manual_ep_num=ep_num, next_ep=ep_num)
        await message.answer(
            f"💡 <b>{ep_num}-qism</b> tanlandi. Endi videoni yuboring:",
            reply_markup=get_admin_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    await message.answer(
        "📹 <b>Videolarni yuboring</b> (bir nechta bo'lsa birdaniga tashlashingiz mumkin).\n"
        "Tugatgach <b>/done</b> deb yozing yoki pastdagi <b>✅ Yakunlash</b> tugmasini bosing."
    )


# ================= 3. SPONSOR KANALLAR BOSHQARUVI =================

@router.callback_query(F.data == "admin_channels")
async def handle_admin_channels_menu(callback: CallbackQuery):
    await callback.answer()
    channels = await db.get_all_sponsor_channels()

    text = "📢 <b>Majburiy obuna (Sponsor) kanallar ro'yxati:</b>\n\n"
    if not channels:
        text += "<i>Hozircha hech qanday kanal ulanmagan.</i>\n\n"
    else:
        for ch in channels:
            status = "🟢 Faol" if ch.get("is_active") else "🔴 Nofaol"
            text += f"▪️ <b>{html.escape(ch['title'])}</b>\n"
            text += f"   ID: <code>{ch['channel_id']}</code> | {status}\n"
            text += f"   Havola: {ch['invite_link']}\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel", style="success")
    )
    for ch in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 O'chirish: {ch['title'][:20]}",
                callback_data=f"del_channel_{ch['channel_id']}",
                style="danger"
            )
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="primary")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "admin_add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddChannelState.channel_id)
    text = (
        "📢 <b>Yangi sponsor kanal qo'shish</b>\n\n"
        "1-qadam: Kanal ID raqamini (yoki @username) kiriting:\n"
        "<i>(Masalan: -1001234567890 yoki @kanal_username)</i>\n\n"
        "⚠️ <i>Eslatma: Bot ushbu kanalda administrator bo'lishi shart!</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddChannelState.channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    from bot.utils import clean_channel_id
    ch_id = clean_channel_id(message.text.strip())
    await state.update_data(channel_id=ch_id)
    await state.set_state(AddChannelState.title)
    await message.answer(
        "2-qadam: Kanal nomini yozing:\n<i>(Masalan: Rasmiy Anime Kanalimiz)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddChannelState.title)
async def process_channel_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AddChannelState.invite_link)
    await message.answer(
        "3-qadam: Kanalga taklif havolasini (linkini) yuboring:\n<i>(Masalan: https://t.me/kanal_username yoki https://t.me/+joinchat...)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddChannelState.invite_link)
async def process_channel_link(message: Message, state: FSMContext):
    link = message.text.strip()
    data = await state.get_data()
    ch_id = data["channel_id"]
    title = data["title"]

    await db.add_sponsor_channel(channel_id=ch_id, title=title, invite_link=link)
    await state.clear()

    await message.answer(
        f"✅ <b>{html.escape(title)}</b> kanali sponsor ro'yxatiga muvaffaqiyatli qo'shildi!",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("del_channel_"))
async def handle_delete_channel(callback: CallbackQuery):
    ch_id = callback.data.replace("del_channel_", "")
    await db.delete_sponsor_channel(ch_id)
    await callback.answer("Kanal o'chirildi!", show_alert=True)
    # Ro'yxatni yangilash
    await handle_admin_channels_menu(callback)


# ================= 4. VIP BERISH =================

@router.callback_query(F.data == "admin_give_vip")
async def start_give_vip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(GiveVipState.user_id)
    text = (
        "💎 <b>Foydalanuvchiga VIP obuna berish</b>\n\n"
        "1-qadam: Foydalanuvchining Telegram ID raqamini kiriting:\n<i>(Masalan: 123456789)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(GiveVipState.user_id)
async def process_vip_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak:")
        return

    user_id = int(message.text)
    user = await db.get_user(user_id)
    if not user:
        await message.answer("⚠️ Ushbu foydalanuvchi botdan hali foydalanmagan. Lekin davom etishingiz mumkin.")

    await state.update_data(user_id=user_id)
    await state.set_state(GiveVipState.days)
    await message.answer(
        f"Foydalanuvchi ID: <code>{user_id}</code>\n\n"
        f"2-qadam: Necha kunga VIP berilsin? (kunlar soni):\n<i>(Masalan: 30 yoki 365)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(GiveVipState.days)
async def process_vip_days(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.answer("❌ Kunlar soni faqat butun son bo'lishi kerak. Masalan: 30")
        return

    days = int(message.text)
    data = await state.get_data()
    target_user_id = data["user_id"]

    success = await db.give_vip(target_user_id, days)
    await state.clear()

    if success:
        await message.answer(
            f"✅ <code>{target_user_id}</code> ID raqamli foydalanuvchiga <b>{days} kunlik VIP</b> berildi!",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        # Foydalanuvchiga xabar jo'natish
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 <b>Tabriklaymiz!</b> Sizga administrator tomonidan <b>{days} kunlik VIP obuna</b> faollashtirildi!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await message.answer(
            "❌ VIP berishda xatolik yuz berdi. Foydalanuvchi mavjudligini tekshiring.",
            reply_markup=get_admin_main_keyboard()
        )


@router.callback_query(F.data.startswith("approve_vip_"))
async def handle_approve_vip(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    days = int(parts[3])

    success = await db.give_vip(target_user_id, days)
    await callback.answer("✅ VIP obuna berildi!", show_alert=True)

    if success:
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎉 <b>Tabriklaymiz!</b> Sizning to'lovingiz muvaffaqiyatli tasdiqlandi!\n\n"
                    f"💎 Sizga <b>{days} kunlik VIP obuna</b> faollashtirildi.\n"
                    f"Endi siz botdagi barcha animelarni homiy kanallarsiz va cheklovlarsiz tomosha qilishingiz mumkin!"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n✅ <b>ADMIN TOMONIDAN TASDIQLANDI ({days} kunlik VIP berildi)!</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("reject_vip_"))
async def handle_reject_vip(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    target_user_id = int(parts[2])

    await callback.answer("❌ To'lov rad etildi.", show_alert=True)
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "❌ <b>Kechirasiz, siz yuborgan to'lov cheki tasdiqlanmadi.</b>\n\n"
                "Iltimos, agar to'lov qilgan bo'lsangiz, admin bilan to'g'ridan-to'g'ri bog'laning:\n"
                "👨🏻‍💻 <b>Admin:</b> @Jahongir02_02"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n❌ <b>ADMIN TOMONIDAN RAD ETILDI!</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ================= 5. STATISTIKA =================

@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    await callback.answer()
    users_count = await db.get_users_count()
    vip_count = await db.get_vip_users_count()
    animes_count = await db.get_animes_count()
    episodes_count = await db.get_episodes_count()
    total_views = await db.get_total_views()
    channels = await db.get_active_sponsor_channels()

    db_status = "🟢 Neon PostgreSQL (Cloud / JSONB Pooler)" if db.is_postgres else "🟡 SQLite (Lokal)"

    text = (
        "📊 <b>Botning to'liq statistikasi:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {users_count:,} ta\n"
        f"💎 <b>VIP a'zolar:</b> {vip_count} ta\n"
        f"🎬 <b>Jami animelar:</b> {animes_count} ta\n"
        f"📼 <b>Yuklangan qismlar:</b> {episodes_count} ta\n"
        f"👁 <b>Umumiy ko'rishlar soni:</b> {total_views:,} marta\n"
        f"📢 <b>Faol sponsor kanallar:</b> {len(channels)} ta\n\n"
        f"🗄 <b>Baza holati:</b>\n<code>{db_status}</code>"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats", style="primary"))
    builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="danger"))

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ================= 6. ANIMELAR RO'YXATI VA BOSHQARISH =================

@router.callback_query(F.data.startswith("admin_list_animes_"))
async def handle_admin_list_animes(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.replace("admin_list_animes_", ""))
    limit = 7
    offset = page * limit

    total = await db.get_animes_count()
    animes = await db.get_animes_paginated(offset=offset, limit=limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    text = (
        f"📋 <b>Botdagi animelar ro'yxati</b> (Jami: {total} ta)\n\n"
        f"Qism yuklash, kanalga qayta postlash yoki o'chirish uchun kerakli animeni tanlang:"
    )
    kb = get_animes_list_keyboard(animes, page, total_pages)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_manage_anime_"))
async def handle_admin_manage_anime(callback: CallbackQuery):
    await callback.answer()
    anime_id = int(callback.data.replace("admin_manage_anime_", ""))
    anime = await db.get_anime(anime_id)
    if not anime:
        await callback.answer("❌ Anime topilmadi!", show_alert=True)
        return

    episodes = await db.get_anime_episodes(anime_id)
    existing_nums = [e["episode_num"] for e in episodes]
    next_ep = max(existing_nums, default=0) + 1
    nums_str = ", ".join(str(n) for n in sorted(existing_nums)) if existing_nums else "Hozircha yo'q"

    text = (
        f"🎬 <b>{html.escape(anime['title'])}</b>\n\n"
        f"🆔 <b>Anime ID:</b> <code>{anime['id']}</code>\n"
        f"📊 <b>Holati:</b> {html.escape(anime.get('status', 'Davom etmoqda'))}\n"
        f"📁 <b>Rejadagi qismlar:</b> {html.escape(anime.get('episodes_count', ''))}\n"
        f"📼 <b>Yuklangan qismlar ({len(existing_nums)} ta):</b> {nums_str}\n"
        f"🎭 <b>Janrlar:</b> {html.escape(anime.get('genres', ''))}\n"
        f"👁 <b>Ko'rishlar soni:</b> {anime.get('views', 0)}\n"
        f"📢 <b>Kanal:</b> {html.escape(anime.get('channel', ''))}\n"
    )
    kb = get_anime_manage_keyboard(anime_id, next_ep)

    try:
        await callback.message.delete()
    except Exception:
        pass

    try:
        await callback.message.answer_photo(
            photo=anime["poster"],
            caption=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )


# ================= 7. XABAR TARQATISH (BROADCAST) =================

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BroadcastState.message)
    text = (
        "✉️ <b>Barcha foydalanuvchilarga xabar tarqatish</b>\n\n"
        "Tarqatmoqchi bo'lgan xabaringizni yuboring (matn, rasm, video yoki post):"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(BroadcastState.message)
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = await db.get_all_users()
    total = len(users)

    status_msg = await message.answer(f"⏳ Xabar tarqatish boshlandi... Jami foydalanuvchilar: {total}")

    sent = 0
    blocked = 0

    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            sent += 1
            await asyncio.sleep(0.05)  # Telegram limitlariga tushmaslik uchun
        except Exception:
            blocked += 1

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"▪️ Yuborildi: {sent} ta\n"
        f"▪️ Yetib bormadi (bloklagan): {blocked} ta",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
    )


# ================= 8. ANIMENI O'CHIRISH =================

@router.callback_query(F.data == "admin_delete_anime")
async def start_delete_anime(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(DeleteAnimeState.anime_id)

    # Oxirgi qo'shilgan 5 ta animeni ko'rsatish
    recent = await db.get_top_animes(limit=5)
    text = "🗑 <b>Animeni o'chirish bo'limi</b>\n\n"
    if recent:
        text += "📌 <i>Oxirgi qo'shilgan ba'zi animelar:</i>\n"
        for a in recent:
            text += f"• ID: <code>{a['id']}</code> — {html.escape(a['title'][:30])}\n"
        text += "\n"

    text += "O'chirmoqchi bo'lgan animengizning <b>ID raqamini</b> kiriting:\n<i>(Masalan: 961)</i>"
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(DeleteAnimeState.anime_id)
async def process_delete_anime_id(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query.isdigit():
        await message.answer(
            "❌ Iltimos, faqat anime ID raqamini kiriting (masalan: 961):",
            reply_markup=get_admin_cancel_keyboard()
        )
        return

    anime_id = int(query)
    anime = await db.get_anime(anime_id)
    if not anime:
        await message.answer(
            f"❌ <b>{anime_id}</b> ID raqamli anime bazadan topilmadi. Qaytadan kiriting:",
            reply_markup=get_admin_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.clear()
    text = (
        f"⚠️ <b>Haqiqatdan ham ushbu animeni o'chirmoqchimisiz?</b>\n\n"
        f"🆔 <b>ID:</b> <code>{anime['id']}</code>\n"
        f"🎬 <b>Nomi:</b> {html.escape(anime['title'])}\n"
        f"📁 <b>Qismlar:</b> {html.escape(anime['episodes_count'])}\n"
        f"👁 <b>Ko'rishlar:</b> {anime.get('views', 0)}\n\n"
        f"<i>Eslatma: Anime o'chirilsa, uning barcha yuklangan qismlari ham bazadan o'chiriladi!</i>"
    )
    await message.answer(text, reply_markup=get_delete_confirm_keyboard(anime_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_del_anime_"))
async def handle_confirm_delete_anime(callback: CallbackQuery):
    anime_id = int(callback.data.replace("confirm_del_anime_", ""))
    anime = await db.get_anime(anime_id)
    title = anime["title"] if anime else f"ID: {anime_id}"

    success = await db.delete_anime(anime_id)
    await callback.answer()

    if success:
        text = f"✅ <b>{html.escape(title)}</b> animesi va barcha qismlari muvaffaqiyatli o'chirildi!"
    else:
        text = f"❌ Animeni o'chirishda xatolik yuz berdi yoki allaqachon o'chirilgan."

    try:
        await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_delete_manga")
async def start_delete_manga(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mangas = await db.get_all_mangas(limit=30)
    if not mangas:
        await callback.message.edit_text(
            "⚠️ Hozirda bazada hech qanday manga mavjud emas.",
            reply_markup=get_admin_main_keyboard()
        )
        return

    await state.set_state(DeleteMangaState.manga_id)
    text = (
        "🗑 <b>Mangani o'chirish bo'limi</b>\n\n"
        "Quyidagi ro'yxatdan o'chirmoqchi bo'lgan mangani tanlang yoki uning <b>ID raqamini</b> yozib yuboring:\n\n"
    )
    for m in mangas[:10]:
        ch_count = m.get("chapters_count", 0)
        text += f"• ID: <code>{m['id']}</code> — <b>{html.escape(m['title'])}</b> ({ch_count} bob)\n"

    await callback.message.edit_text(text, reply_markup=get_admin_delete_manga_keyboard(mangas[:10]), parse_mode="HTML")


@router.callback_query(F.data.startswith("del_manga_select_"))
async def handle_del_manga_select(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    manga_id = int(callback.data.replace("del_manga_select_", ""))
    manga = await db.get_manga(manga_id)
    if not manga:
        await callback.message.edit_text("❌ Manga topilmadi!", reply_markup=get_admin_main_keyboard())
        return

    await state.clear()
    ch_count = manga.get("chapters_count", 0)
    text = (
        f"⚠️ <b>Haqiqatdan ham ushbu mangani butunlay o'chirmoqchimisiz?</b>\n\n"
        f"🆔 <b>ID:</b> <code>{manga['id']}</code>\n"
        f"📖 <b>Nomi:</b> {html.escape(manga['title'])}\n"
        f"📑 <b>Mavjud boblar:</b> {ch_count} ta\n"
        f"🎭 <b>Janri:</b> {html.escape(manga.get('genre', ''))}\n\n"
        f"<i>Eslatma: Manga o'chirilsa, uning barcha boblari va Mini App ma'lumotlar bazasidan butunlay yo'qoladi!</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_confirm_delete_manga_keyboard(manga_id), parse_mode="HTML")


@router.message(DeleteMangaState.manga_id)
async def process_delete_manga_id(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query.isdigit():
        await message.answer(
            "❌ Iltimos, faqat manga ID raqamini kiriting (masalan: 2):",
            reply_markup=get_admin_cancel_keyboard()
        )
        return

    manga_id = int(query)
    manga = await db.get_manga(manga_id)
    if not manga:
        await message.answer(
            f"❌ <b>{manga_id}</b> ID raqamli manga bazadan topilmadi. Qaytadan kiriting:",
            reply_markup=get_admin_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.clear()
    ch_count = manga.get("chapters_count", 0)
    text = (
        f"⚠️ <b>Haqiqatdan ham ushbu mangani butunlay o'chirmoqchimisiz?</b>\n\n"
        f"🆔 <b>ID:</b> <code>{manga['id']}</code>\n"
        f"📖 <b>Nomi:</b> {html.escape(manga['title'])}\n"
        f"📑 <b>Mavjud boblar:</b> {ch_count} ta\n"
        f"🎭 <b>Janri:</b> {html.escape(manga.get('genre', ''))}\n\n"
        f"<i>Eslatma: Manga o'chirilsa, uning barcha boblari va Mini App ma'lumotlar bazasidan butunlay yo'qoladi!</i>"
    )
    await message.answer(text, reply_markup=get_confirm_delete_manga_keyboard(manga_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_del_manga_"))
async def handle_confirm_delete_manga(callback: CallbackQuery):
    manga_id = int(callback.data.replace("confirm_del_manga_", ""))
    manga = await db.get_manga(manga_id)
    title = manga["title"] if manga else f"ID: {manga_id}"

    success = await db.delete_manga(manga_id)
    await callback.answer()

    if success:
        await sync_mangas_json()
        asyncio.create_task(push_to_github())
        text = f"✅ <b>{html.escape(title)}</b> mangasi va barcha ma'lumotlari muvaffaqiyatli o'chirildi hamda Mini App sinxronlashtirildi!"
    else:
        text = "❌ Mangani o'chirishda xatolik yuz berdi yoki allaqachon o'chirilgan."

    try:
        await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


# ================= MANGA VA SHORTS YUKLASH BO'LIMI =================

import os
import re
import json
import shutil
import zipfile
import logging

logger = logging.getLogger("AdminHandler")


async def push_to_github():
    """VPS da ma'lumotlarni avtomatik GitHub Pages ga push qilish"""
    try:
        cmd = (
            "git add -A && "
            "(git diff --cached --quiet || git commit -m 'sync: update shorts & manga data') && "
            "(git pull --rebase --autostash origin main || git rebase --abort || true) && "
            "git push origin main && "
            "git push --force origin main:gh-pages"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"Error pushing to github: code={proc.returncode}, err={stderr.decode('utf-8', errors='ignore')}")
        else:
            logger.info("Successfully pushed manga & shorts data to GitHub (main & gh-pages)")
    except Exception as e:
        logger.error(f"Error pushing to github: {e}")


async def sync_mangas_json():
    """Mini App uchun mangas.json faylini yangilash"""
    mangas = await db.get_all_mangas(limit=200)
    data = []
    for m in mangas:
        m_data = m.get("data") or {}
        if isinstance(m_data, str):
            try:
                m_data = json.loads(m_data)
            except Exception:
                m_data = {}
        data.append({
            "id": m["id"],
            "title": m["title"],
            "cover": m["cover"],
            "genre": m["genre"],
            "status": m["status"],
            "chapters": m.get("chapters_count", 1),
            "rating": m.get("rating", "4.9"),
            "desc": m.get("description", ""),
            "data": m_data
        })
    paths = [
        "data/mangas.json",
        "manga/mangas.json",
        "miniapp/manga/mangas.json",
        "docs/manga/mangas.json",
        "/var/www/html/manga/mangas.json",
        "/var/www/html/data/mangas.json"
    ]
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


async def sync_shorts_json():
    """Mini App uchun shorts.json faylini yangilash"""
    shorts = await db.get_all_shorts(limit=200)
    data = []
    for s in shorts:
        data.append({
            "id": s["id"],
            "title": s["title"],
            "video_url": s.get("video_url") or f"videos/short_{s['id']}.mp4",
            "file_id": s.get("video_file_id", ""),
            "caption": s.get("caption", ""),
            "sound": s.get("sound_title", "AniMovie Asl ovoz"),
            "creator": s.get("creator", "@Ani_Movei_UZ"),
            "likes": s.get("likes_count", 0),
            "comments": s.get("comments_count", 0)
        })
    paths = [
        "data/shorts.json",
        "shorts/shorts.json",
        "miniapp/shorts/shorts.json",
        "docs/shorts/shorts.json",
        "/var/www/html/shorts/shorts.json",
        "/var/www/html/data/shorts.json"
    ]
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# 1. Manga yuklash
@router.callback_query(F.data == "admin_add_manga")
async def start_add_manga(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddMangaState.title)
    text = (
        "📖 <b>Yangi manga qo'shish</b>\n\n"
        "Manga nomini kiriting (Masalan: <code>Solo Leveling</code> yoki <code>Attack on Titan</code>):"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddMangaState.title)
async def process_manga_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AddMangaState.cover)
    text = (
        f"📖 Manga nomi: <b>{html.escape(title)}</b>\n\n"
        "Endi manga muqovasi (poster) rasmini yuboring yoki rasm havolasini (URL) yozing:"
    )
    await message.answer(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddMangaState.cover)
async def process_manga_cover(message: Message, state: FSMContext, bot: Bot):
    cover_url = ""
    if message.photo:
        photo = message.photo[-1]
        try:
            cover_filename = f"cover_{photo.file_unique_id}.jpg"
            primary_cover = os.path.join("manga/covers", cover_filename)
            os.makedirs("manga/covers", exist_ok=True)
            await bot.download(photo, destination=primary_cover)
            for d in ["docs/manga/covers", "miniapp/manga/covers"]:
                try:
                    os.makedirs(d, exist_ok=True)
                    shutil.copyfile(primary_cover, os.path.join(d, cover_filename))
                except Exception:
                    pass
            cover_url = f"https://ithac4290-sys.github.io/animoviebot/manga/covers/{cover_filename}"
        except Exception:
            try:
                file_info = await bot.get_file(photo.file_id)
                cover_url = f"https://api.telegram.org/file/bot{config.bot_token}/{file_info.file_path}"
            except Exception:
                cover_url = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500"
        await state.update_data(cover_file_id=photo.file_id)
    elif message.document and (
        (message.document.mime_type and message.document.mime_type.startswith("image/")) or
        message.document.file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ):
        doc = message.document
        try:
            cover_filename = f"cover_{doc.file_unique_id}.jpg"
            primary_cover = os.path.join("manga/covers", cover_filename)
            os.makedirs("manga/covers", exist_ok=True)
            await bot.download(doc, destination=primary_cover)
            for d in ["docs/manga/covers", "miniapp/manga/covers"]:
                try:
                    os.makedirs(d, exist_ok=True)
                    shutil.copyfile(primary_cover, os.path.join(d, cover_filename))
                except Exception:
                    pass
            cover_url = f"https://ithac4290-sys.github.io/animoviebot/manga/covers/{cover_filename}"
        except Exception:
            cover_url = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500"
        await state.update_data(cover_file_id=doc.file_id)
    elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        cover_url = message.text.strip()
    else:
        await message.answer("⚠️ Iltimos, muqova rasmini yuboring yoki rasm URL havolasini kiriting:")
        return

    await state.update_data(cover=cover_url)
    await state.set_state(AddMangaState.genre)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Jangari", callback_data="genre_action", style="primary"),
        InlineKeyboardButton(text="🔮 Fantastika", callback_data="genre_fantasy", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="🏃 Sarguzasht", callback_data="genre_adventure", style="primary"),
        InlineKeyboardButton(text="❤️ Romantika", callback_data="genre_romance", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="😂 Komediya", callback_data="genre_comedy", style="primary")
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))

    await message.answer("🎭 Manga janrini tanlang yoki matn ko'rinishida yozing:", reply_markup=builder.as_markup())


@router.callback_query(AddMangaState.genre, F.data.startswith("genre_"))
async def process_manga_genre_cb(callback: CallbackQuery, state: FSMContext):
    genre_map = {
        "genre_action": "Jangari",
        "genre_fantasy": "Fantastika",
        "genre_adventure": "Sarguzasht",
        "genre_romance": "Romantika",
        "genre_comedy": "Komediya"
    }
    genre = genre_map.get(callback.data, "Jangari")
    await state.update_data(genre=genre)
    await state.set_state(AddMangaState.manga_type)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇰🇷 Manhwa", callback_data="mtype_Manhwa", style="primary"),
        InlineKeyboardButton(text="🇯🇵 Manga", callback_data="mtype_Manga", style="primary"),
        InlineKeyboardButton(text="🇨🇳 Manhua", callback_data="mtype_Manhua", style="primary")
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))
    await callback.message.edit_text("📚 <b>Manga turini tanlang:</b>", reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(AddMangaState.genre)
async def process_manga_genre_text(message: Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await state.set_state(AddMangaState.manga_type)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇰🇷 Manhwa", callback_data="mtype_Manhwa", style="primary"),
        InlineKeyboardButton(text="🇯🇵 Manga", callback_data="mtype_Manga", style="primary"),
        InlineKeyboardButton(text="🇨🇳 Manhua", callback_data="mtype_Manhua", style="primary")
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))
    await message.answer("📚 <b>Manga turini tanlang:</b>", reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(AddMangaState.manga_type, F.data.startswith("mtype_"))
async def process_manga_type_cb(callback: CallbackQuery, state: FSMContext):
    m_type = callback.data.split("_", 1)[1]
    await state.update_data(manga_type=m_type)
    await state.set_state(AddMangaState.status)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Davom etmoqda", callback_data="mstatus_ongoing", style="primary"),
        InlineKeyboardButton(text="🔴 Tugallangan", callback_data="mstatus_completed", style="success")
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger"))
    await callback.message.edit_text("📌 Manga holatini tanlang:", reply_markup=builder.as_markup())


@router.callback_query(AddMangaState.status, F.data.startswith("mstatus_"))
async def process_manga_status_cb(callback: CallbackQuery, state: FSMContext):
    status = "Davom etmoqda" if callback.data == "mstatus_ongoing" else "Tugallangan"
    await state.update_data(status=status)
    await state.set_state(AddMangaState.chapters_count)
    await callback.message.edit_text(
        "🔢 <b>Jami boblar sonini kiriting</b> (Masalan: <code>150</code>):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddMangaState.chapters_count)
async def process_manga_chapters(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("⚠️ Iltimos, faqat raqam kiriting (masalan: 120):")
        return
    await state.update_data(chapters_count=int(raw))
    await state.set_state(AddMangaState.description)
    await message.answer(
        "📝 <b>Manga haqida qisqacha tavsif yozing:</b>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddMangaState.description)
async def process_manga_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    data = await state.get_data()
    title = data.get("title", "Manga")
    cover = data.get("cover", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500")
    genre = data.get("genre", "Jangari")
    manga_type = data.get("manga_type", "Manhwa")
    status = data.get("status", "Davom etmoqda")
    chapters_count = data.get("chapters_count", 1)

    m_id = await db.add_manga(
        title=title,
        cover=cover,
        genre=genre,
        status=status,
        chapters_count=chapters_count,
        description=desc,
        rating="4.9",
        data={"type": manga_type, "lang": "Uzbek"}
    )

    await sync_mangas_json()
    asyncio.create_task(push_to_github())
    await state.clear()

    # Kanalga post tayyorlash va yuborish (https://t.me/AniMovie_manga)
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or config.bot_username
    manga_channel = config.manga_channel_id

    channel_caption = (
        f"• <b>{html.escape(title)}</b>\n"
        f"╭━━━━━━━━━━━━━━━━━━━━━\n"
        f"▸ <b>Janr :</b> {html.escape(genre)}\n"
        f"▸ <b>Turi :</b> {html.escape(manga_type)}\n"
        f"▸ <b>Til :</b> Uzbek\n"
        f"▸ <b>Holati :</b> {html.escape(status)}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Asosiy kanal:</b> {manga_channel}"
    )

    posted_to_channel = False
    error_msg = ""
    try:
        channel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📚 Hoziroq O'qish 📚",
                        url=f"https://t.me/{bot_username}?start=manga_{m_id}",
                        style="success"
                    )
                ]
            ]
        )
        await message.bot.send_photo(
            chat_id=manga_channel,
            photo=cover,
            caption=channel_caption,
            reply_markup=channel_kb,
            parse_mode="HTML"
        )
        posted_to_channel = True
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error posting manga to channel: {e}")

    post_status_str = f"📢 <b>{manga_channel} kanaliga post muvaffaqiyatli yuborildi!</b>" if posted_to_channel else f"⚠️ <i>Kanalga yuborishda ogohlantirish: {html.escape(error_msg)}</i>"

    text = (
        f"✅ <b>Manga muvaffaqiyatli saqlandi va Mini App'ga qo'shildi!</b>\n\n"
        f"🆔 <b>ID:</b> <code>{m_id}</code>\n"
        f"📖 <b>Nomi:</b> {html.escape(title)}\n"
        f"🎭 <b>Janri:</b> {genre}\n"
        f"📚 <b>Turi:</b> {manga_type}\n"
        f"📌 <b>Holati:</b> {status}\n"
        f"🔢 <b>Boblar soni:</b> {chapters_count} ta\n"
        f"📝 <b>Tavsif:</b> {html.escape(desc[:100])}...\n\n"
        f"{post_status_str}\n\n"
        f"Endi ushbu mangaga birinchi bob sahifalarini yuklashingiz mumkin:"
    )
    await message.answer(
        text,
        reply_markup=get_admin_after_chapter_keyboard(m_id, 1),
        parse_mode="HTML"
    )


# 1.1 Manga bobi va sahifalarini yuklash
@router.callback_query(F.data == "admin_add_chapter")
async def start_add_chapter(callback: CallbackQuery, state: FSMContext):
    mangas = await db.get_all_mangas(limit=30)
    if not mangas:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Yangi manga yaratish", callback_data="admin_add_manga", style="success"))
        builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="danger"))
        await callback.message.edit_text(
            "⚠️ <b>Hozircha birorta ham manga yaratilmagan!</b>\n\n"
            "Bob yuklashdan oldin yangi manga profilini yarating.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    text = (
        "📑 <b>Manga bobi va sahifalarini yuklash</b>\n\n"
        "Qaysi manga uchun yangi bob yuklamoqchisiz? Quyidagilardan birini tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_recent_mangas_keyboard(mangas), parse_mode="HTML")


@router.callback_query(F.data.startswith("select_manga_"))
async def handle_pick_manga_cb(callback: CallbackQuery, state: FSMContext):
    manga_id = int(callback.data.split("_")[-1])
    manga = await db.get_manga(manga_id)
    if not manga:
        await callback.answer("⚠️ Manga topilmadi!", show_alert=True)
        return

    m_data = manga.get("data") or {}
    if isinstance(m_data, str):
        try:
            m_data = json.loads(m_data)
        except Exception:
            m_data = {}
    chapters = m_data.get("chapters", [])
    existing_nums = [c.get("chapter_num", 0) for c in chapters if isinstance(c, dict)]
    next_ch = (max(existing_nums) + 1) if existing_nums else 1

    await state.update_data(manga_id=manga_id, manga_title=manga["title"], pages=[])
    await state.set_state(AddChapterState.chapter_num)

    text = (
        f"📖 Tanlangan manga: <b>{html.escape(manga['title'])}</b>\n"
        f"Mavjud boblar: <b>{len(existing_nums)}</b> ta\n\n"
        f"Yuklanadigan <b>bob raqamini</b> kiriting (Masalan: <code>{next_ch}</code>):"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("quick_add_ch_"))
async def handle_quick_add_ch_cb(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    manga_id = int(parts[3])
    next_ch = int(parts[4])
    manga = await db.get_manga(manga_id)
    if not manga:
        await callback.answer("⚠️ Manga topilmadi!", show_alert=True)
        return

    await state.update_data(manga_id=manga_id, manga_title=manga["title"], chapter_num=next_ch, pages=[])
    await state.set_state(AddChapterState.pages)

    text = (
        f"📑 <b>{html.escape(manga['title'])} — {next_ch}-bob</b>\n\n"
        f"Ushbu bobning sahifalarini yuboring:\n"
        f"• 📑 <b>PDF fayl</b> (barcha sahifalar jamlangan bitta PDF)\n"
        f"• 📦 <b>ZIP / CBZ arxiv</b>\n"
        f"• 📸 <b>Rasmlar</b> (bittalab yoki foto-albom ko'rinishida)\n\n"
        f"<i>Barcha sahifalarni yuborib bo'lgach, <b>[ ✅ Yuklashni yakunlash ]</b> tugmasini bosing!</i>\n\n"
        f"<i>📸 Qabul qilingan sahifalar: 0 ta</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_finish_chapter_keyboard(0), parse_mode="HTML")


@router.message(AddChapterState.chapter_num)
async def process_chapter_num(message: Message, state: FSMContext, bot: Bot):
    # Agar admin bob raqamini yozmasdan to'g'ridan-to'g'ri PDF, ZIP yoki rasm yuborsa
    if message.document:
        doc = message.document
        filename = doc.file_name or "chapter.pdf"
        match = re.search(r'(?:bob|ch|chapter)[\s_-]*(\d+)', filename, re.IGNORECASE) or re.search(r'(\d+)[\s_-]*(?:bob|ch|chapter)', filename, re.IGNORECASE) or re.search(r'(\d+)', filename)
        ch_num = int(match.group(1)) if match else 1
        await state.update_data(chapter_num=ch_num, pages=[])
        await state.set_state(AddChapterState.pages)
        return await process_chapter_document(message, state, bot)

    if message.photo:
        await state.update_data(chapter_num=1, pages=[])
        await state.set_state(AddChapterState.pages)
        return await process_chapter_photo(message, state)

    if not message.text:
        await message.answer("⚠️ Iltimos, bob raqamini son shaklida kiriting yoki to'g'ridan-to'g'ri PDF/ZIP fayl yuboring:", parse_mode="HTML")
        return

    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("⚠️ Iltimos, bob raqamini faqat son shaklida kiriting (Masalan: <code>1</code>):", parse_mode="HTML")
        return

    ch_num = int(raw)
    data = await state.get_data()
    manga_title = data.get("manga_title", "Manga")
    await state.update_data(chapter_num=ch_num, pages=[])
    await state.set_state(AddChapterState.pages)

    text = (
        f"📑 <b>{html.escape(manga_title)} — {ch_num}-bob</b>\n\n"
        f"Ushbu bobning sahifalarini yuboring:\n"
        f"• 📑 <b>PDF fayl</b> (barcha sahifalar jamlangan bitta PDF)\n"
        f"• 📦 <b>ZIP / CBZ arxiv</b>\n"
        f"• 📸 <b>Rasmlar</b> (bittalab yoki foto-albom ko'rinishida)\n\n"
        f"<i>Barcha sahifalarni yuborib bo'lgach, <b>[ ✅ Yuklashni yakunlash ]</b> tugmasini bosing!</i>\n\n"
        f"<i>📸 Qabul qilingan sahifalar: 0 ta</i>"
    )
    await message.answer(text, reply_markup=get_admin_finish_chapter_keyboard(0), parse_mode="HTML")


@router.message(AddChapterState.pages, F.document)
async def process_chapter_document(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    filename = doc.file_name or "chapter.pdf"
    file_ext = os.path.splitext(filename)[1].lower()

    data = await state.get_data()
    manga_id = data.get("manga_id")
    manga_title = data.get("manga_title", "Manga")
    ch_num = data.get("chapter_num", 1)
    pages = data.get("pages", [])

    # Bob raqamini fayl nomidan aniqlash (Masalan: "BOB 186", "186-bob", "ch186", "chapter 186")
    match = re.search(r'(?:bob|ch|chapter)[\s_-]*(\d+)', filename, re.IGNORECASE) or re.search(r'(\d+)[\s_-]*(?:bob|ch|chapter)', filename, re.IGNORECASE)
    if match:
        extracted_num = int(match.group(1))
        ch_num = extracted_num
        await state.update_data(chapter_num=ch_num)

    # 1. PDF Fayl
    if file_ext == ".pdf":
        if doc.file_size and doc.file_size > 20 * 1024 * 1024:
            await message.answer(
                "⚠️ <b>Fayl hajmi 20 MB dan katta!</b>\n\n"
                "Telegram Bot API cheklovi tufayli bot 20 MB dan ortiq fayllarni to'g'ridan-to'g'ri yuklab ololmaydi.\n"
                "Iltimos, PDF hajmini biroz ixchamlang (compress) yoki bobni rasmlar (ZIP arxiv yoki foto) shaklida yuboring.",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
            return

        status_msg = await message.answer(
            f"⏳ <b>{html.escape(filename)}</b> qabul qilindi.\n"
            f"PDF sahifalari ajratib olinmoqda, iltimos kuting...",
            parse_mode="HTML"
        )
        try:
            temp_pdf = f"data/temp_{message.chat.id}_{doc.file_unique_id}.pdf"
            os.makedirs("data", exist_ok=True)
            await bot.download(doc, destination=temp_pdf)

            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            pdf_doc = fitz.open(temp_pdf)
            total_pages = len(pdf_doc)

            pages_rel_dir = f"pages/manga_{manga_id}_ch_{ch_num}"
            target_dirs = [
                f"manga/{pages_rel_dir}",
                f"docs/manga/{pages_rel_dir}",
                f"miniapp/manga/{pages_rel_dir}"
            ]
            for d in target_dirs:
                os.makedirs(d, exist_ok=True)

            start_idx = len(pages)
            for idx in range(total_pages):
                page = pdf_doc.load_page(idx)
                pix = page.get_pixmap(dpi=150)
                img_name = f"p_{start_idx + idx + 1}.jpg"
                primary_path = os.path.join(target_dirs[0], img_name)
                pix.save(primary_path)
                for d in target_dirs[1:]:
                    try:
                        shutil.copyfile(primary_path, os.path.join(d, img_name))
                    except Exception:
                        pass
                page_url = f"https://ithac4290-sys.github.io/animoviebot/manga/{pages_rel_dir}/{img_name}"
                pages.append(page_url)

            pdf_doc.close()
            try:
                os.remove(temp_pdf)
            except Exception:
                pass

            await state.update_data(pages=pages)
            await status_msg.edit_text(
                f"✅ <b>PDF muvaffaqiyatli qabul qilindi!</b>\n\n"
                f"📖 <b>Manga:</b> {html.escape(manga_title)}\n"
                f"📑 <b>Bob:</b> {ch_num}-bob\n"
                f"📸 <b>Ajratib olingan yangi sahifalar:</b> {total_pages} ta\n"
                f"📊 <b>Jami sahifalar:</b> {len(pages)} ta\n\n"
                f"Barcha sahifalar tayyor bo'lsa, quyidagi tugmani bosing:",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error processing chapter PDF: {e}")
            await status_msg.edit_text(
                f"❌ PDF faylni qayta ishlashda xatolik yuz berdi: {html.escape(str(e))}\n"
                f"Iltimos, boshqa PDF yoki rasmlar shaklida yuboring.",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
        return

    # 2. ZIP / CBZ Arxivi
    elif file_ext in [".zip", ".cbz"]:
        status_msg = await message.answer(
            f"⏳ <b>{html.escape(filename)}</b> arxivi ochilmoqda...",
            parse_mode="HTML"
        )
        try:
            temp_zip = f"data/temp_{message.chat.id}_{doc.file_unique_id}.zip"
            os.makedirs("data", exist_ok=True)
            await bot.download(doc, destination=temp_zip)

            pages_rel_dir = f"pages/manga_{manga_id}_ch_{ch_num}"
            target_dirs = [
                f"manga/{pages_rel_dir}",
                f"docs/manga/{pages_rel_dir}",
                f"miniapp/manga/{pages_rel_dir}"
            ]
            for d in target_dirs:
                os.makedirs(d, exist_ok=True)

            with zipfile.ZipFile(temp_zip, 'r') as zf:
                valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
                img_names = sorted([n for n in zf.namelist() if n.lower().endswith(valid_exts) and not n.startswith('__MACOSX')])
                for idx, name in enumerate(img_names):
                    extracted_bytes = zf.read(name)
                    img_name = f"p_{idx + 1}.jpg"
                    primary_path = os.path.join(target_dirs[0], img_name)
                    with open(primary_path, 'wb') as f:
                        f.write(extracted_bytes)
                    for d in target_dirs[1:]:
                        try:
                            shutil.copyfile(primary_path, os.path.join(d, img_name))
                        except Exception:
                            pass
                    page_url = f"https://ithac4290-sys.github.io/animoviebot/manga/{pages_rel_dir}/{img_name}"
                    pages.append(page_url)

            try:
                os.remove(temp_zip)
            except Exception:
                pass

            await state.update_data(pages=pages)
            await status_msg.edit_text(
                f"✅ <b>Arxivdan {len(img_names)} ta sahifa muvaffaqiyatli ajratib olindi!</b>\n\n"
                f"📖 <b>Manga:</b> {html.escape(manga_title)}\n"
                f"📑 <b>Bob:</b> {ch_num}-bob\n\n"
                f"Barcha sahifalar tayyor bo'lsa, quyidagi tugmani bosing:",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error processing chapter ZIP: {e}")
            await status_msg.edit_text(
                f"❌ Arxivni ochishda xatolik yuz berdi: {html.escape(str(e))}",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
        return

    # 3. Rasm fayl (JPG, PNG, WEBP)
    elif file_ext in [".jpg", ".jpeg", ".png", ".webp"] or (doc.mime_type and doc.mime_type.startswith("image/")):
        try:
            pages_rel_dir = f"pages/manga_{manga_id}_ch_{ch_num}"
            target_dirs = [
                f"manga/{pages_rel_dir}",
                f"docs/manga/{pages_rel_dir}",
                f"miniapp/manga/{pages_rel_dir}"
            ]
            for d in target_dirs:
                os.makedirs(d, exist_ok=True)
            img_name = f"p_{len(pages) + 1}.jpg"
            primary_path = os.path.join(target_dirs[0], img_name)
            await bot.download(doc, destination=primary_path)
            for d in target_dirs[1:]:
                try:
                    shutil.copyfile(primary_path, os.path.join(d, img_name))
                except Exception:
                    pass
            page_url = f"https://ithac4290-sys.github.io/animoviebot/manga/{pages_rel_dir}/{img_name}"
            pages.append(page_url)
            await state.update_data(pages=pages)
            await message.answer(
                f"📸 <b>{len(pages)}-sahifa qabul qilindi!</b>\n\n"
                f"📖 <i>{html.escape(manga_title)} ({ch_num}-bob)</i>\n"
                f"Keyingi sahifani yuboring yoki barchasi tayyor bo'lsa yakunlang:",
                reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error saving image doc: {e}")
        return

    else:
        await message.answer(
            "⚠️ <b>Noma'lum formatdagi fayl!</b>\n\n"
            "Iltimos, bob sahifalari uchun:\n"
            "• 📑 <b>PDF</b> fayl (masalan: <code>BOB 186.pdf</code>)\n"
            "• 📦 <b>ZIP / CBZ</b> arxiv\n"
            "• 📸 <b>Rasmlar (foto yoki rasm fayl)</b> yuboring.",
            reply_markup=get_admin_finish_chapter_keyboard(len(pages)),
            parse_mode="HTML"
        )


@router.message(AddChapterState.pages, F.photo)
async def process_chapter_photo(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    data = await state.get_data()
    manga_id = data.get("manga_id")
    manga_title = data.get("manga_title", "Manga")
    ch_num = data.get("chapter_num", 1)
    pages = data.get("pages", [])

    pages_rel_dir = f"pages/manga_{manga_id}_ch_{ch_num}"
    target_dirs = [
        f"manga/{pages_rel_dir}",
        f"docs/manga/{pages_rel_dir}",
        f"miniapp/manga/{pages_rel_dir}"
    ]
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)

    img_name = f"p_{len(pages) + 1}.jpg"
    primary_path = os.path.join(target_dirs[0], img_name)
    try:
        await bot.download(photo, destination=primary_path)
        for d in target_dirs[1:]:
            try:
                shutil.copyfile(primary_path, os.path.join(d, img_name))
            except Exception:
                pass
        page_url = f"https://ithac4290-sys.github.io/animoviebot/manga/{pages_rel_dir}/{img_name}"
    except Exception:
        try:
            f = await bot.get_file(photo.file_id)
            page_url = f"https://api.telegram.org/file/bot{config.bot_token}/{f.file_path}"
        except Exception:
            page_url = photo.file_id

    pages.append(page_url)
    await state.update_data(pages=pages)

    text = (
        f"📸 <b>{len(pages)}-sahifa qabul qilindi!</b>\n\n"
        f"📖 <i>{html.escape(manga_title)} ({ch_num}-bob)</i>\n"
        f"Keyingi sahifani yuboring yoki barchasi tayyor bo'lsa yakunlang:"
    )
    await message.answer(text, reply_markup=get_admin_finish_chapter_keyboard(len(pages)), parse_mode="HTML")


@router.callback_query(AddChapterState.pages, F.data == "admin_finish_chapter")
async def handle_finish_chapter_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    manga_id = data.get("manga_id")
    manga_title = data.get("manga_title", "Manga")
    ch_num = data.get("chapter_num", 1)
    pages = data.get("pages", [])

    if not pages:
        await callback.answer("⚠️ Hech bo'lmaganda 1 ta sahifa rasmini yuboring!", show_alert=True)
        return

    await db.add_manga_chapter(
        manga_id=manga_id,
        chapter_num=ch_num,
        pages=pages,
        title=f"{ch_num}-bob"
    )

    await sync_mangas_json()
    asyncio.create_task(push_to_github())
    await state.clear()

    text = (
        f"🎉 <b>Manga bobi muvaffaqiyatli saqlandi!</b>\n\n"
        f"📖 <b>Manga:</b> {html.escape(manga_title)}\n"
        f"📑 <b>Bob:</b> {ch_num}-bob\n"
        f"📄 <b>Sahifalar soni:</b> {len(pages)} ta\n"
        f"✅ <i>Sahifalar PostgreSQL bazasiga va Manga Mini App'ga saqlandi!</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_after_chapter_keyboard(manga_id, ch_num + 1),
        parse_mode="HTML"
    )



# 2. Shorts yuklash
@router.callback_query(F.data == "admin_add_shorts")
async def start_add_shorts(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddShortsState.video)
    text = (
        "⚡️ <b>Yangi Shorts video yuklash</b>\n\n"
        "Shorts uchun qisqa videoni (MP4) yuboring:\n"
        "<i>Eslatma: Vertikal video (9:16 formatda) bo'lishi tavsiya etiladi.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddShortsState.video)
async def process_shorts_video(message: Message, state: FSMContext, bot: Bot):
    if not message.video:
        await message.answer("⚠️ Iltimos, video fayl yuboring:")
        return

    video = message.video
    file_id = video.file_id

    video_rel_url = f"videos/short_{video.file_unique_id}.mp4"
    dest_dirs = [
        "shorts/videos",
        "docs/shorts/videos",
        "miniapp/shorts/videos",
        "/var/www/html/shorts/videos"
    ]
    try:
        os.makedirs(dest_dirs[0], exist_ok=True)
        primary_file = os.path.join(dest_dirs[0], f"short_{video.file_unique_id}.mp4")
        await bot.download(video, destination=primary_file)
        for d in dest_dirs[1:]:
            try:
                os.makedirs(d, exist_ok=True)
                shutil.copyfile(primary_file, os.path.join(d, f"short_{video.file_unique_id}.mp4"))
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error saving short video: {e}")

    await state.update_data(video_file_id=file_id, video_url=video_rel_url)
    await state.set_state(AddShortsState.title)
    text = (
        "✅ Video qabul qilindi!\n\n"
        "Endi ushbu shortning <b>sarlavhasini</b> kiriting (Masalan: <code>Qora Klever: Asta vs Dante</code>):"
    )
    await message.answer(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddShortsState.title)
async def process_shorts_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AddShortsState.caption)
    text = (
        f"🎬 Sarlavha: <b>{html.escape(title)}</b>\n\n"
        "Endi video <b>tavsifi va xeshteglarini</b> kiriting (Masalan: <code>Epik jang sahnasi! #blackclover #anime #asta</code>):"
    )
    await message.answer(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddShortsState.caption)
async def process_shorts_caption(message: Message, state: FSMContext):
    caption = message.text.strip()
    await state.update_data(caption=caption)
    await state.set_state(AddShortsState.sound)
    text = (
        "🎵 <b>Musiqa / Ovoz nomini kiriting:</b>\n"
        "(Masalan: <code>Haruka Mirai — Epic Remix</code> yoki <code>AniMovie Asl ovoz</code>):"
    )
    await message.answer(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


@router.message(AddShortsState.sound)
async def process_shorts_sound(message: Message, state: FSMContext):
    sound = message.text.strip()
    data = await state.get_data()
    title = data.get("title", "Shorts Video")
    video_file_id = data.get("video_file_id", "")
    video_url = data.get("video_url", "videos/short1.mp4")
    caption = data.get("caption", "")

    s_id = await db.add_short(
        title=title,
        video_file_id=video_file_id,
        video_url=video_url,
        caption=caption,
        sound_title=sound,
        creator="@Ani_Movei_UZ"
    )

    await sync_shorts_json()
    asyncio.create_task(push_to_github())
    await state.clear()

    text = (
        f"✅ <b>Shorts video muvaffaqiyatli yuklandi va Mini App'ga qo'shildi!</b>\n\n"
        f"🆔 <b>ID:</b> <code>{s_id}</code>\n"
        f"⚡️ <b>Sarlavha:</b> {html.escape(title)}\n"
        f"📝 <b>Tavsif:</b> {html.escape(caption)}\n"
        f"🎵 <b>Musiqa:</b> {html.escape(sound)}"
    )
    await message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")

