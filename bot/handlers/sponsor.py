import re
import html
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import db
from bot.states import SponsorBotState
from bot.multibot import MultiBotManager
from bot.keyboards import (
    get_sponsor_menu_keyboard,
    get_sponsor_cancel_keyboard,
    get_my_bots_keyboard
)

logger = logging.getLogger("SponsorHandler")
router = Router()

TOKEN_PATTERN = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{30,50}$")


@router.message(Command("sponsor", "homiy"))
async def cmd_sponsor(message: Message, state: FSMContext):
    """Buyruq orqali homiy bo'lish bo'limiga kirish"""
    await state.clear()
    await show_sponsor_menu(message, message.from_user.id)


@router.callback_query(F.data == "btn_sponsor")
async def callback_sponsor(callback: CallbackQuery, state: FSMContext):
    """Tugma orqali homiy bo'lish bo'limiga kirish"""
    await state.clear()
    await show_sponsor_menu(callback, callback.from_user.id)
    await callback.answer()


async def show_sponsor_menu(message_or_callback: Message | CallbackQuery, user_id: int):
    """Homiy bo'lish asosiy sahifasini ko'rsatish"""
    user_bots = await db.get_user_sponsor_bots(user_id)

    text = (
        "🤝 <b>Homiy bo'lish — Shaxsiy botingizni yarating!</b>\n\n"
        "Siz o'z Telegram botingizni bizning tizimga ulab, xuddi bizning botimiz kabi "
        "to'liq ishlovchi shaxsiy Anime botiga ega bo'lishingiz mumkin!\n\n"
        "⚡️ <b>Qanday imkoniyatlarga ega bo'lasiz?</b>\n"
        "• Barcha mavjud animelar va qismlar sizning botingizda ham ochiladi\n"
        "• Qidiruv (nomi, kodi, janri va rasmi bo'yicha)\n"
        "• Manga va Shorts bo'limlari\n"
        "• Foydalanuvchilar to'g'ridan-to'g'ri sizning botingizda foydalanishadi\n"
        "• Bot ulash <b>mutlaqo bepul</b> va darhol ishga tushadi!\n"
    )

    if user_bots:
        text += "\n📋 <b>Siz ulagan botlar:</b>\n"
        for idx, b in enumerate(user_bots, 1):
            status = "✅ Faol" if b.get("is_active") else "⏸ To'xtatilgan"
            uname = b.get("bot_username", "bot")
            text += f"{idx}. @{uname} — {status}\n"

    kb = get_sponsor_menu_keyboard(has_bots=bool(user_bots))

    if isinstance(message_or_callback, CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await message_or_callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "sponsor_add_bot")
async def callback_sponsor_add_bot(callback: CallbackQuery, state: FSMContext):
    """Bot tokenini so'rash yo'riqnomasi"""
    await state.set_state(SponsorBotState.waiting_for_token)

    text = (
        "🤖 <b>Telegram Bot API Tokenini yuboring</b>\n\n"
        "O'z botingizni ulash uchun quyidagi 4 ta oddiy qadamni bajaring:\n\n"
        "1️⃣ Telegramda @BotFather ga kiring\n"
        "2️⃣ <code>/newbot</code> buyrug'ini yuboring\n"
        "3️⃣ Botingizga <b>nom</b> (masalan: <i>Mening Anime Botim</i>) va "
        "<b>username</b> (masalan: <i>my_animovi_bot</i>) bering\n"
        "4️⃣ @BotFather taqdim etgan <b>HTTP API Token</b> ni nusxalab, shu yerga xabar sifatida yuboring.\n\n"
        "📌 <i>Token namunasi:</i>\n"
        "<code>7123456789:AAHk1_xyzabc...-90qwe</code>\n\n"
        "<i>Token xavfsiz saqlanadi va faqat botingizni ishga tushirish uchun xizmat qiladi.</i>"
    )

    kb = get_sponsor_cancel_keyboard()
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "sponsor_cancel")
async def callback_sponsor_cancel(callback: CallbackQuery, state: FSMContext):
    """Homiy tokeni kiritishni bekor qilish"""
    await state.clear()
    await callback.answer("Amal bekor qilindi.")
    await show_sponsor_menu(callback, callback.from_user.id)


@router.callback_query(F.data == "sponsor_my_bots")
async def callback_sponsor_my_bots(callback: CallbackQuery, state: FSMContext):
    """Ulangan botlar ro'yxatini ko'rish va boshqarish"""
    await state.clear()
    user_id = callback.from_user.id
    user_bots = await db.get_user_sponsor_bots(user_id)

    if not user_bots:
        await callback.answer("Sizda hali ulangan botlar yo'q!", show_alert=True)
        await show_sponsor_menu(callback, user_id)
        return

    text = (
        "📋 <b>Sizning ulangan botlaringiz:</b>\n\n"
        "Quyidagi ro'yxatdan botingizga o'tishingiz yoki kerak bo'lmasa o'chirib tashlashingiz mumkin:"
    )

    kb = get_my_bots_keyboard(user_bots)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor_del_"))
async def callback_sponsor_del_bot(callback: CallbackQuery):
    """Homiy botni to'xtatish va o'chirish"""
    try:
        bot_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri parametr!", show_alert=True)
        return

    user_id = callback.from_user.id
    # Botni to'xtatish
    await MultiBotManager.stop_bot(bot_id)
    # Bazadan o'chirish
    await db.delete_sponsor_bot(bot_id, user_id)

    await callback.answer("✅ Botingiz muvaffaqiyatli to'xtatildi va tizimdan o'chirildi!", show_alert=True)
    # Yangilangan menyuni ko'rsatish
    await show_sponsor_menu(callback, user_id)


@router.message(SponsorBotState.waiting_for_token)
async def process_sponsor_bot_token(message: Message, state: FSMContext):
    """Foydalanuvchi yuborgan bot tokenini qabul qilish va tekshirish"""
    token = (message.text or "").strip()

    # Bekor qilish so'zi bo'lsa
    if token.lower() in ["/cancel", "bekor qilish", "cancel", "bekor"]:
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_sponsor_menu_keyboard())
        return

    # 1. Format tekshiruvi
    if not TOKEN_PATTERN.match(token) and ":" not in token:
        await message.answer(
            "❌ <b>Noto'g'ri token formati!</b>\n\n"
            "Iltimos, @BotFather bergan tokenni to'liq nusxalab yuboring.\n"
            "Misol: <code>7123456789:AAHk...-XYZ123abc</code>\n\n"
            "<i>Bekor qilish uchun /cancel deb yozing yoki pastdagi tugmani bosing:</i>",
            reply_markup=get_sponsor_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    status_msg = await message.answer(
        "🔄 <b>Token tekshirilmoqda va bot ulanmoqda...</b>\n<i>Iltimos, bir necha soniya kuting...</i>",
        parse_mode="HTML"
    )

    # 2. MultiBotManager orqali botni tekshirish va ishga tushirish
    user_id = message.from_user.id
    success, msg_text, bot_info = await MultiBotManager.start_bot(token, owner_id=user_id)

    if not success or not bot_info:
        await status_msg.edit_text(
            f"{msg_text}\n\n<i>Qaytadan urinib ko'rishingiz yoki bekor qilishingiz mumkin:</i>",
            reply_markup=get_sponsor_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    # 3. Bazaga saqlash
    await db.add_sponsor_bot(
        owner_id=user_id,
        bot_token=token,
        bot_id=bot_info.id,
        bot_username=bot_info.username or f"bot_{bot_info.id}",
        bot_name=bot_info.first_name
    )

    # 4. State holatini tozalash
    await state.clear()

    # 5. Muvaffaqiyat xabari
    success_builder = InlineKeyboardBuilder()
    success_builder.row(
        InlineKeyboardButton(
            text="🚀 Botingizga o'tish",
            url=f"https://t.me/{bot_info.username}"
        )
    )
    success_builder.row(
        InlineKeyboardButton(
            text="🏠 Asosiy menyu",
            callback_data="btn_home",
            style="danger"
        )
    )

    congrats_text = (
        "🎉 <b>Tabriklaymiz! Botingiz muvaffaqiyatli ishga tushirildi!</b>\n\n"
        f"🤖 <b>Bot nomi:</b> {html.escape(bot_info.first_name)}\n"
        f"🔗 <b>Username:</b> @{bot_info.username}\n"
        f"🆔 <b>Bot ID:</b> <code>{bot_info.id}</code>\n\n"
        "✨ <b>Botingiz to'liq tayyor va ishlamoqda!</b>\n"
        f"Endi @{bot_info.username} ga o'ting va <b>/start</b> buyrug'ini bosing — "
        "barcha animelar, qidiruv va imkoniyatlar sizning shaxsiy botingizda ham ishlaydi!"
    )

    await status_msg.edit_text(
        congrats_text,
        reply_markup=success_builder.as_markup(),
        parse_mode="HTML"
    )
