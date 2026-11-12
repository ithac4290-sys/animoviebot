import html
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
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
    DeleteAnimeState
)
from bot.keyboards import (
    get_admin_main_keyboard,
    get_admin_cancel_keyboard,
    get_status_keyboard,
    get_channel_post_keyboard,
    get_delete_confirm_keyboard
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


@router.message(AddAnimeState.poster, F.photo)
async def process_anime_poster(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(poster=photo_file_id)
    await state.set_state(AddAnimeState.status)
    await message.answer(
        "3-qadam: Anime holatini tanlang yoki yozing:",
        reply_markup=get_status_keyboard()
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
    await message.answer(
        f"6-qadam: Asosiy kanal username'ini yozing:\n<i>(Masalan: {config.default_channel_id} yoki @QorakleverS2)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAnimeState.channel)
async def process_anime_channel_finish(message: Message, state: FSMContext, bot: Bot):
    channel = message.text.strip()
    if not channel.startswith("@") and not channel.startswith("-100"):
        channel = f"@{channel}"

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
        channel=channel
    )

    await state.clear()

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    # 2. 1-rasmdagi dizaynda kanal postini tayyorlash
    channel_post_caption = (
        f"{html.escape(title)}\n\n"
        f"<blockquote>• Holati: {html.escape(status)}\n"
        f"• Anime: {html.escape(episodes_count)}\n"
        f"• Janrlari: {html.escape(genres)}\n"
        f"• Kanal: {html.escape(channel)}</blockquote>"
    )

    channel_kb = get_channel_post_keyboard(bot_username, anime_id)

    # 3. Kanalga avtomatik post yuborish
    post_channel_target = config.default_channel_id or channel
    posted_to_channel = False
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

    # 4. Adminga hisobot berish
    success_text = (
        f"✅ <b>Yangi anime muvaffaqiyatli saqlandi!</b>\n\n"
        f"🆔 <b>Anime ID:</b> <code>{anime_id}</code>\n"
        f"📌 <b>Nomi:</b> {html.escape(title)}\n"
        f"📎 <b>Link:</b> https://t.me/{bot_username}?start={anime_id}\n\n"
    )

    if posted_to_channel:
        success_text += f"📢 <b>{post_channel_target} kanaliga avtomatik post joylandi!</b>"
    else:
        success_text += (
            f"⚠️ <i>Kanalga ({post_channel_target}) avtomatik post joylanmadi.</i>\n"
            f"Sababi: Bot kanalda administrator qilinmagan bo'lishi mumkin.\n"
            f"Xatolik: {html.escape(error_msg if 'error_msg' in locals() else 'Noma\'lum')}"
        )

    await message.answer(success_text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


# ================= 2. QISM YUKLASH =================

@router.callback_query(F.data == "admin_add_episode")
async def start_add_episode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddEpisodeState.anime_id)
    text = (
        "🎬 <b>Anime qismini yuklash</b>\n\n"
        "1-qadam: Anime ID raqamini kiriting:\n<i>(Masalan: 961)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_cancel_keyboard(), parse_mode="HTML")


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

    await state.update_data(anime_id=anime_id, anime_title=anime["title"])
    await state.set_state(AddEpisodeState.episode_num)
    await message.answer(
        f"Tanlangan anime: <b>{html.escape(anime['title'])}</b>\n\n"
        f"2-qadam: Nechanchi qism ekanligini kiriting (raqam):\n<i>(Masalan: 1 yoki 2)</i>",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddEpisodeState.episode_num)
async def process_episode_num(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Qism raqami faqat butun son bo'lishi kerak. Masalan: 1")
        return

    ep_num = int(message.text)
    await state.update_data(episode_num=ep_num)
    await state.set_state(AddEpisodeState.video)
    await message.answer(
        f"3-qadam: <b>{ep_num}-qism</b> videosini (yoki fayl ko'rinishida) yuboring:",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddEpisodeState.video, F.video | F.document)
async def process_episode_file(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = data["anime_id"]
    ep_num = data["episode_num"]
    anime_title = data.get("anime_title", "Anime")

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

    await state.clear()
    await message.answer(
        f"✅ <b>{html.escape(anime_title)}</b> animesining <b>{ep_num}-qismi</b> muvaffaqiyatli saqlandi!",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
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
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel")
    )
    for ch in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 O'chirish: {ch['title'][:20]}",
                callback_data=f"del_channel_{ch['channel_id']}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home")
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
    ch_id = message.text.strip()
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


# ================= 5. STATISTIKA =================

@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    await callback.answer()
    users_count = await db.get_users_count()
    animes_count = await db.get_animes_count()
    episodes_count = await db.get_episodes_count()
    channels = await db.get_active_sponsor_channels()

    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {users_count} ta\n"
        f"🎬 <b>Animelar:</b> {animes_count} ta\n"
        f"📼 <b>Yuklangan qismlar:</b> {episodes_count} ta\n"
        f"📢 <b>Faol sponsor kanallar:</b> {len(channels)} ta\n"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ================= 6. XABAR TARQATISH (BROADCAST) =================

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


# ================= 7. ANIMENI O'CHIRISH =================

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

    await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")

