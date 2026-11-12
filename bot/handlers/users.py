import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import db
from bot.keyboards import (
    get_main_menu_keyboard,
    get_anime_keyboard,
    get_subscription_keyboard,
    get_cabinet_keyboard,
    get_back_home_keyboard
)
from bot.utils import check_user_subscriptions

router = Router()


def get_welcome_text(full_name: str) -> str:
    """3-rasmdagi bosh sahifa matni"""
    escaped_name = html.escape(full_name or "Анимешник")
    return (
        f"✋🏻 <b>Assalomu aleykum hurmatli '{escaped_name}' botimizga xush kelibsiz.</b>\n\n"
        f"📄 <i>Botimizda barcha animelarni osongina @animelar_uzbekcha_si kanalidan yuklab olib tomosha qilishingiz mumkin.</i>\n\n"
        f"<u>Botimizdagi ba'zi buyruqlar:</u>\n"
        f"<blockquote>/top - 📄 Animelar ro'yxati.\n"
        f"/help - ☎️ Qo'llab-quvvatlash.\n"
        f"/vip - 💎 VIP Obuna haqida.\n"
        f"/qollanma - 📚 Botdan foydalanish.</blockquote>\n\n"
        f"‼️ Botga to'g'ridan-to'g'ri anime kodi yoki nomini yozishingiz mumkin."
    )


def format_anime_caption(anime: dict, bot_username: str) -> str:
    """2-rasmdagi anime caption formati"""
    title = html.escape(anime.get("title", ""))
    status = html.escape(anime.get("status", "Davom etmoqda"))
    channel = html.escape(anime.get("channel", f"@{bot_username}"))
    anime_id = anime.get("id")

    return (
        f"{title}\n\n"
        f"<blockquote>• Holati: {status}\n"
        f"• Sifat - 720p, 1080p\n"
        f"• {channel}</blockquote>\n\n"
        f"🏷 Botimiz: @{bot_username}\n"
        f"📮 Anime ID: {anime_id}\n"
        f"📎 Link: https://t.me/{bot_username}?start={anime_id}"
    )


# ================= /start BUYRUG'I =================

@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext):
    await state.clear()
    args = command.args
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    # Agar parametr bo'lsa (Deep-link: masalan /start 961)
    if args:
        clean_arg = args.strip()
        # "anime_961" yoki "961"
        if clean_arg.startswith("anime_"):
            clean_arg = clean_arg.replace("anime_", "")

        if clean_arg.isdigit():
            anime_id = int(clean_arg)
            await show_anime_by_id(message, anime_id, bot, bot_username)
            return

    # Parametr bo'lmaganda: ASOSIY BOSH MENYU (3-rasm dizayni)
    text = get_welcome_text(message.from_user.full_name)
    kb = get_main_menu_keyboard(bot_username)
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
        kb = get_subscription_keyboard(unsubbed)
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
    episodes_count = anime.get("episodes_count", "12")
    kb = get_anime_keyboard(anime_id, episodes_count)

    poster = anime.get("poster")
    if isinstance(message_or_query, Message):
        await message_or_query.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_query.message.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")


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

    anime = await db.get_anime(anime_id)
    episode = await db.get_episode(anime_id, ep_num)

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    if not episode:
        await callback.answer(f"⚠️ {ep_num}-qism tez orada yuklanadi!", show_alert=True)
        return

    await callback.answer(f"⏳ {ep_num}-qism yuborilmoqda...")

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


# ================= MATN ORQALI ANIME QIDIRISH (ID yoki NOM) =================

@router.message(F.text & ~F.text.startswith("/"))
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
    for anime in results:
        text += f"▪️ <b>{html.escape(anime['title'])}</b>\n"
        text += f"   Kod: <code>{anime['id']}</code> | Tomosha: /start_{anime['id']}\n\n"

    text += "<i>Ko'rmoqchi bo'lgan animengiz kodini yozing yoki /start_ID ustiga bosing.</i>"
    await message.answer(text, parse_mode="HTML")


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
async def handle_vip_info(event: Message | CallbackQuery):
    text = (
        "💎 <b>VIP OBUNA HAQIDA MA'LUMOT</b>\n\n"
        "VIP a'zolik sizga qanday imkoniyatlarni beradi?\n"
        "• 🚫 Barcha majburiy obuna va homiy kanallardan ozod bo'lish\n"
        "• ⚡️ Animelarni yuqori tezlikda yuklab olish\n"
        "• 🍿 Premyeralarni birinchilardan bo'lib ko'rish\n"
        "• 🎖 Maxsus VIP maqomi va nishoni\n\n"
        "💵 <b>VIP Obuna narxlari:</b>\n"
        "• 1 oylik: 15,000 so'm\n"
        "• 3 oylik: 35,000 so'm\n"
        "• Doimiy (cheksiz): 70,000 so'm\n\n"
        "📞 VIP obunani faollashtirish uchun admin bilan bog'laning: @animelar_admini"
    )
    kb = get_back_home_keyboard()
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


# 3. /top - Animelar ro'yxati
@router.message(Command("top"))
async def handle_top_animes(message: Message):
    top_list = await db.get_top_animes(limit=10)
    if not top_list:
        await message.answer("📄 Hozircha bazada animelar mavjud emas.")
        return

    text = "🔥 <b>TOP-10 Eng ko'p ko'rilgan animelar:</b>\n\n"
    for i, a in enumerate(top_list, 1):
        views = a.get("views", 0)
        title = html.escape(a.get("title", ""))
        anime_id = a.get("id")
        text += f"<b>{i}.</b> {title}\n"
        text += f"   👁 {views} ko'rish | Kod: <code>{anime_id}</code> | /start_{anime_id}\n\n"

    await message.answer(text, parse_mode="HTML")


# 4. /help - Qo'llab-quvvatlash
@router.message(Command("help"))
async def handle_help(message: Message):
    text = (
        "☎️ <b>Qo'llab-quvvatlash xizmati</b>\n\n"
        "Botda biror muammo, xatolik yoki savollaringiz bo'lsa, adminlarimiz bilan bog'lanishingiz mumkin:\n\n"
        "👨🏻‍💻 <b>Admin:</b> @animelar_admini\n"
        "📢 <b>Kanalimiz:</b> @animelar_uzbekcha_si\n"
        "💬 <b>Guruhimiz:</b> @animelar_uzbekcha_chat"
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


# 6. 📄 Manga kurish
@router.callback_query(F.data == "btn_manga")
async def handle_manga(callback: CallbackQuery):
    await callback.answer()
    text = (
        "📄 <b>Manga mutolaa bo'limi</b>\n\n"
        "Tez kunda botimizda eng sara o'zbekcha tarjima qilingan mangalarni ham o'qishingiz mumkin bo'ladi!\n\n"
        "Yangiliklarni kanalimizda kuzatib boring: @animelar_uzbekcha_si"
    )
    await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")


# 7. 🔴 Shorts kurish
@router.callback_query(F.data == "btn_shorts")
async def handle_shorts(callback: CallbackQuery):
    await callback.answer()
    text = (
        "🔴 <b>Anime Shorts & Lavhalar</b>\n\n"
        "Eng qiziqarli anime qisqa videolari va lahzalarini bizning maxsus kanalimizda tomosha qiling:\n\n"
        "👉 https://t.me/animelar_uzbekcha_si"
    )
    await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")


# 8. ⬅️ Bosh menyuga qaytish
@router.callback_query(F.data == "btn_home")
async def handle_back_home(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username
    text = get_welcome_text(callback.from_user.full_name)
    kb = get_main_menu_keyboard(bot_username)
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")


# 9. ✅ Obunani tekshirish callback
@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)

    if is_subbed:
        await callback.answer("✅ Barcha kanallarga a'zo bo'lgansiz! Rahmat.", show_alert=True)
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username
        text = get_welcome_text(callback.from_user.full_name)
        kb = get_main_menu_keyboard(bot_username)
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        kb = get_subscription_keyboard(unsubbed)
        await callback.message.edit_reply_markup(reply_markup=kb)
