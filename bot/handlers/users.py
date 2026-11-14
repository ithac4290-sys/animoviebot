import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
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
    get_admin_vip_approval_keyboard
)
from bot.states import VipPaymentState
from bot.utils import check_user_subscriptions

router = Router()


def get_welcome_text(full_name: str) -> str:
    """3-rasmdagi bosh sahifa matni"""
    escaped_name = html.escape(full_name or "Анимешник")
    return (
        f"✋🏻 <b>Assalomu aleykum hurmatli '{escaped_name}' botimizga xush kelibsiz.</b>\n\n"
        f"📄 <i>Botimizda barcha animelarni osongina @Ani_Movei_UZ kanalidan yuklab olib tomosha qilishingiz mumkin.</i>\n\n"
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


# 6. 📄 Manga kurish
@router.callback_query(F.data == "btn_manga")
async def handle_manga(callback: CallbackQuery):
    await callback.answer()
    text = (
        "📄 <b>Manga mutolaa bo'limi</b>\n\n"
        "Tez kunda botimizda eng sara o'zbekcha tarjima qilingan mangalarni ham o'qishingiz mumkin bo'ladi!\n\n"
        "Yangiliklarni kanalimizda kuzatib boring: @Ani_Movei_UZ"
    )
    await callback.message.edit_text(text, reply_markup=get_back_home_keyboard(), parse_mode="HTML")


# 7. 🔴 Shorts kurish
@router.callback_query(F.data == "btn_shorts")
async def handle_shorts(callback: CallbackQuery):
    await callback.answer()
    text = (
        "🔴 <b>Anime Shorts & Lavhalar</b>\n\n"
        "Eng qiziqarli anime qisqa videolari va lahzalarini bizning maxsus kanalimizda tomosha qiling:\n\n"
        "👉 https://t.me/Ani_Movei_UZ"
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
@router.callback_query(F.data.startswith("check_sub"))
async def handle_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_subbed, unsubbed = await check_user_subscriptions(bot, user_id)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username

    target_anime_id = None
    if callback.data.startswith("check_sub_"):
        raw_id = callback.data.replace("check_sub_", "")
        if raw_id.isdigit():
            target_anime_id = int(raw_id)

    if is_subbed:
        await callback.answer("✅ Barcha kanallarga a'zo bo'lgansiz! Rahmat.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass

        # Agar foydalanuvchi anime ko'rish uchun tekshirgan bo'lsa, o'sha animeni darhol ochish!
        if target_anime_id:
            await show_anime_by_id(callback, target_anime_id, bot, bot_username)
        else:
            text = get_welcome_text(callback.from_user.full_name)
            kb = get_main_menu_keyboard(bot_username)
            await callback.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        if target_anime_id:
            builder = InlineKeyboardBuilder()
            for idx, ch in enumerate(unsubbed, 1):
                title = ch.get("title", f"Kanal #{idx}")
                link = ch.get("invite_link", "https://t.me")
                builder.row(InlineKeyboardButton(text=f"📢 {title}", url=link))
            builder.row(InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub_{target_anime_id}"))
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        else:
            kb = get_subscription_keyboard(unsubbed)
            await callback.message.edit_reply_markup(reply_markup=kb)


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
