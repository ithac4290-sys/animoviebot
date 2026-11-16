import re
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from bot.config import config


def get_main_menu_keyboard(bot_username: str, is_vip: bool = False, user_id: int = 0) -> InlineKeyboardMarkup:
    """
    1. ASOSIY BOSH MENYU:
    - 1-qator: [ 🔍 𝗔𝗻𝗶𝗺𝗲 𝗶𝘇𝗹𝗮𝘀𝗵 ]
    - 2-qator: [ 📖 𝗠𝗮𝗻𝗴𝗮 𝗸𝗼'𝗿𝗶𝘀𝗵 ] | [ ⚡️ 𝗦𝗵𝗼𝗿𝘁𝘀 𝗸𝗼'𝗿𝗶𝘀𝗵 ]
      (Faqat VIP foydalanuvchilar uchun WebApp ochiladi, oddiy foydalanuvchilarga VIP ogohlantirish beriladi)
    - 3-qator: [ 👤 𝗞𝗮𝗯𝗶𝗻𝗲𝘁 ] | [ 👑 𝗩𝗜𝗣 𝗢𝗯𝘂𝗻𝗮 ]
    """
    builder = InlineKeyboardBuilder()

    # 1-qator: 🔍 Anime izlash
    builder.row(
        InlineKeyboardButton(
            text="🔍 𝗔𝗻𝗶𝗺𝗲 𝗶𝘇𝗹𝗮𝘀𝗵",
            callback_data="btn_search_menu"
        )
    )

    # 2-qator: 📖 Manga ko'rish | ⚡️ Shorts ko'rish
    manga_base = config.manga_webapp_url
    shorts_base = config.shorts_webapp_url
    sep = "&" if "?" in manga_base else "?"
    manga_url = f"{manga_base}{sep}vip=1&user_id={user_id}&v=15"
    sep_s = "&" if "?" in shorts_base else "?"
    shorts_url = f"{shorts_base}{sep_s}vip=1&user_id={user_id}&v=15"

    if is_vip:
        manga_btn = InlineKeyboardButton(text="📖 𝗠𝗮𝗻𝗴𝗮 𝗸𝗼'𝗿𝗶𝘀𝗵", web_app=WebAppInfo(url=manga_url))
        shorts_btn = InlineKeyboardButton(text="⚡️ 𝗦𝗵𝗼𝗿𝘁𝘀 𝗸𝗼'𝗿𝗶𝘀𝗵", web_app=WebAppInfo(url=shorts_url))
    else:
        manga_btn = InlineKeyboardButton(text="📖 𝗠𝗮𝗻𝗴𝗮 [VIP 🔒]", callback_data="vip_required_manga")
        shorts_btn = InlineKeyboardButton(text="⚡️ 𝗦𝗵𝗼𝗿𝘁𝘀 [VIP 🔒]", callback_data="vip_required_shorts")

    builder.row(manga_btn, shorts_btn)

    # 3-qator: 👤 Kabinet | 👑 VIP Obuna
    builder.row(
        InlineKeyboardButton(text="👤 𝗞𝗮𝗯𝗶𝗻𝗲𝘁", callback_data="btn_cabinet"),
        InlineKeyboardButton(text="👑 𝗩𝗜𝗣 𝗢𝗯𝘂𝗻𝗮", callback_data="btn_vip")
    )

    return builder.as_markup()


def get_search_type_keyboard() -> InlineKeyboardMarkup:
    """
    Foydalanuvchi yuborgan rasm bo'yicha qidiruv tipi tugmalari:
    - 1-qator: 🏷Anime nomi orqali | ⏱ So'ngi yuklanganlar
    - 2-qator: 💬Janr orqali qidirish
    - 3-qator: 📌 Kod orqali | 👁 Eng ko'p ko'rilgan
    - 4-qator: 🖼Rasm orqali qidirish
    - 5-qator: 📚 Barcha animelar
    - 6-qator: ⬅️ Bosh menyu
    """
    builder = InlineKeyboardBuilder()

    # 1-qator
    builder.row(
        InlineKeyboardButton(text="🏷Anime nomi orqali", callback_data="search_by_name", style="primary"),
        InlineKeyboardButton(text="⏱ So'ngi yuklanganlar", callback_data="search_latest", style="primary")
    )
    # 2-qator
    builder.row(
        InlineKeyboardButton(text="💬Janr orqali qidirish", callback_data="search_genres", style="primary")
    )
    # 3-qator
    builder.row(
        InlineKeyboardButton(text="📌 Kod orqali", callback_data="search_by_code", style="primary"),
        InlineKeyboardButton(text="👁 Eng ko'p ko'rilgan", callback_data="search_top_views", style="primary")
    )
    # 4-qator
    builder.row(
        InlineKeyboardButton(text="🖼Rasm orqali qidirish", callback_data="search_by_image", style="primary")
    )
    # 5-qator
    builder.row(
        InlineKeyboardButton(text="📚 Barcha animelar", callback_data="search_all_animes_0", style="primary")
    )
    # 6-qator
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home")
    )

    return builder.as_markup()


def get_genres_keyboard() -> InlineKeyboardMarkup:
    """Janrlar bo'yicha qidirish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Jangari", callback_data="genre_Jangari", style="primary"),
        InlineKeyboardButton(text="🧙‍♂️ Fantastika", callback_data="genre_Fantastika", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="😂 Komediya", callback_data="genre_Komediya", style="primary"),
        InlineKeyboardButton(text="🎭 Drama", callback_data="genre_Drama", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="❤️ Romantika", callback_data="genre_Romantika", style="primary"),
        InlineKeyboardButton(text="🏃 Sarguzasht", callback_data="genre_Sarguzasht", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="🔮 Sehr-jodu", callback_data="genre_Sehr-jodu", style="primary"),
        InlineKeyboardButton(text="🎒 Maktab", callback_data="genre_Maktab", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="👻 Dahshat", callback_data="genre_Dahshat", style="primary"),
        InlineKeyboardButton(text="🕵️ Detektiv", callback_data="genre_Detektiv", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Qidiruv menyusiga qaytish", callback_data="btn_search_menu")
    )
    return builder.as_markup()


def get_animes_pagination_keyboard(animes: List[Dict[str, Any]], page: int, total_pages: int, prefix: str = "search_all_animes_") -> InlineKeyboardMarkup:
    """Animelar ro'yxatini sahifalab ko'rsatish tugmalari"""
    builder = InlineKeyboardBuilder()
    for a in animes:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 {a['title'][:28]}",
                callback_data=f"open_anime_{a['id']}",
                style="primary"
            )
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"{prefix}{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}/{max(total_pages, 1)}", callback_data="ignore"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"{prefix}{page+1}"))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(text="⬅️ Qidiruv menyusi", callback_data="btn_search_menu"),
        InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="btn_home")
    )
    return builder.as_markup()


def get_search_cancel_keyboard() -> InlineKeyboardMarkup:
    """Qidiruvni bekor qilish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_search_menu")
    )
    return builder.as_markup()


def get_ai_image_confirmation_keyboard(candidates: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """AI rasm qidiruvida topilgan animelarni tasdiqlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    if len(candidates) == 1:
        c = candidates[0]
        anime_id = c["anime"]["id"]
        builder.row(
            InlineKeyboardButton(text="✅ Ha, aynan shu!", callback_data=f"ai_confirm_{anime_id}")
        )
        builder.row(
            InlineKeyboardButton(text="❌ Yo'q, boshqasi", callback_data="ai_reject_search")
        )
    else:
        for idx, c in enumerate(candidates, 1):
            anime_id = c["anime"]["id"]
            sim = c["similarity"]
            title = c["anime"].get("title", f"Anime #{anime_id}")
            if len(title) > 28:
                title = title[:25] + "..."
            builder.row(
                InlineKeyboardButton(
                    text=f"{idx}️⃣ {title} ({sim}%)",
                    callback_data=f"ai_confirm_{anime_id}"
                )
            )
        builder.row(
            InlineKeyboardButton(text="❌ Hech biri emas", callback_data="ai_reject_search")
        )
    return builder.as_markup()


def get_ai_image_retry_keyboard() -> InlineKeyboardMarkup:
    """AI rasm qidiruvida natija topilmaganda yoki takrorlash uchun klaviatura"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Boshqa rasm yuborish", callback_data="search_by_image")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_search_menu")
    )
    return builder.as_markup()


def get_anime_keyboard(
    anime_id: int,
    episodes_list: Optional[List[int]] = None,
    page: int = 1,
    per_page: int = 20,
    current_ep: Optional[int] = None
) -> InlineKeyboardMarkup:
    """
    ANIME MENYUSI VA QISMLAR RO'YXATI (20 tadan sahifalash):
    - Tanlangan/joriy qism: [ 📀 ] - {ep}
    - Boshqa qismlar: faqat raqam ({ep}) 4 ustunli gridda
    - Pastki qatorda 3 ta tugma bir qatorda: [ ⬅️ Oldingi ] [ ❌ Yopish ] [ ➡️ Keyingi ]
    """
    builder = InlineKeyboardBuilder()

    if episodes_list and len(episodes_list) > 0:
        sorted_episodes = sorted(list(set(episodes_list)))
        total_episodes = len(sorted_episodes)
        total_pages = max(1, (total_episodes + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        if current_ep is None:
            current_ep = sorted_episodes[0]

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_episodes = sorted_episodes[start_idx:end_idx]

        episode_buttons = []
        for ep in page_episodes:
            if ep == current_ep:
                btn_text = f"[ 📀 ] - {ep}"
            else:
                btn_text = f"{ep}"

            episode_buttons.append(
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"play_{anime_id}_{ep}_{page}"
                )
            )

        # 4 tadan ustun (grid) qilib joylashtirish
        builder.add(*episode_buttons)
        builder.adjust(4)

        # Pastki navigatsiya qatori: ⬅️ Oldingi | ❌ Yopish | ➡️ Keyingi
        if total_pages > 1:
            prev_cb = f"ep_page_{anime_id}_{page - 1}_{current_ep}" if page > 1 else "ep_first_page_alert"
            next_cb = f"ep_page_{anime_id}_{page + 1}_{current_ep}" if page < total_pages else "ep_last_page_alert"

            builder.row(
                InlineKeyboardButton(text="⬅️ Oldingi", callback_data=prev_cb),
                InlineKeyboardButton(text="❌ Yopish", callback_data="close_anime_view"),
                InlineKeyboardButton(text="➡️ Keyingi", callback_data=next_cb)
            )
        else:
            builder.row(
                InlineKeyboardButton(text="❌ Yopish", callback_data="close_anime_view")
            )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⏳ Qismlar tez orada yuklanadi",
                callback_data="episodes_coming_soon"
            )
        )
        builder.row(
            InlineKeyboardButton(text="❌ Yopish", callback_data="close_anime_view")
        )

    return builder.as_markup()


def get_channel_post_keyboard(bot_username: str, anime_id: int) -> InlineKeyboardMarkup:
    """
    2. KANALGA AVTOMATIK POST TUGMALARI (1-rasm dizayni):
    1. ▶️ Tomosha qilish -> https://t.me/BOT_USERNAME?start=ANIME_ID (success / yashil)
    2. 📚 Barcha qismlar -> https://t.me/BOT_USERNAME?start=ANIME_ID (primary / ko'k)
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="▶️ 𝗧𝗼𝗺𝗼𝘀𝗵𝗮 𝗾𝗶𝗹𝗶𝘀𝗵",
            url=f"https://t.me/{bot_username}?start={anime_id}",
            style="success"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 𝗕𝗮𝗿𝗰𝗵𝗮 𝗾𝗶𝘀𝗺𝗹𝗮𝗿",
            url=f"https://t.me/{bot_username}?start={anime_id}",
            style="primary"
        )
    )

    return builder.as_markup()


def get_subscription_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Majburiy obuna sponsor kanallar tugmalari"""
    builder = InlineKeyboardBuilder()

    for idx, ch in enumerate(channels, 1):
        title = ch.get("title", f"Kanal #{idx}")
        link = ch.get("invite_link", "https://t.me")
        builder.row(
            InlineKeyboardButton(text=f"📢 {title}", url=link, style="primary")
        )

    builder.row(
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription", style="success")
    )

    return builder.as_markup()


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Anime holatini tanlash (Admin)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Davom etmoqda", callback_data="status_davom", style="primary"),
        InlineKeyboardButton(text="Tugallangan", callback_data="status_tugallangan", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin asosiy paneli tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi anime", callback_data="admin_add_anime", style="success"),
        InlineKeyboardButton(text="🎬 Qism yuklash", callback_data="admin_add_episode", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="📖 Yangi manga", callback_data="admin_add_manga", style="primary"),
        InlineKeyboardButton(text="📑 Manga bobi yuklash", callback_data="admin_add_chapter", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="⚡️ Shorts yuklash", callback_data="admin_add_shorts", style="primary"),
        InlineKeyboardButton(text="📋 Animelar ro'yxati", callback_data="admin_list_animes_0", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data="admin_delete_anime", style="danger"),
        InlineKeyboardButton(text="📢 Sponsor kanallar", callback_data="admin_channels", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="💎 VIP berish", callback_data="admin_give_vip", style="success"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast", style="primary")
    )
    return builder.as_markup()


def get_admin_channel_select_keyboard(default_channel: str) -> InlineKeyboardMarkup:
    """Kanal tanlash tugmasi (standart kanalni bir bosish bilan tanlash)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"📢 Standart kanal ({default_channel})", callback_data="use_default_channel", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_recent_animes_keyboard(animes: List[Dict[str, Any]], action_prefix: str = "select_anime_") -> InlineKeyboardMarkup:
    """Qism yuklash yoki boshqarish uchun animelar tezkor tugmalari"""
    builder = InlineKeyboardBuilder()
    for a in animes:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 {a['id']}. {a['title'][:26]}",
                callback_data=f"{action_prefix}{a['id']}",
                style="primary"
            )
        )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_after_episode_keyboard(anime_id: int, next_ep: int) -> InlineKeyboardMarkup:
    """Qism yuklangandan so'ng navbatdagi qismni tezkor yuklash tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"➕ Keyingi {next_ep}-qismni yuklash",
            callback_data=f"quick_add_ep_{anime_id}_{next_ep}",
            style="success"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🎬 Boshqa anime tanlash", callback_data="admin_add_episode", style="primary"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="primary")
    )
    return builder.as_markup()


def get_admin_recent_mangas_keyboard(mangas: List[Dict[str, Any]], action_prefix: str = "select_manga_") -> InlineKeyboardMarkup:
    """Bob yuklash uchun mangalar ro'yxati tugmalari"""
    builder = InlineKeyboardBuilder()
    for m in mangas:
        ch_count = m.get("chapters_count", 0)
        builder.row(
            InlineKeyboardButton(
                text=f"📖 {m['id']}. {m['title'][:24]} ({ch_count} bob)",
                callback_data=f"{action_prefix}{m['id']}",
                style="primary"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Yangi manga yaratish", callback_data="admin_add_manga", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_finish_chapter_keyboard(pages_count: int = 0) -> InlineKeyboardMarkup:
    """Manga bobi sahifalarini yuklashni yakunlash tugmasi"""
    builder = InlineKeyboardBuilder()
    if pages_count > 0:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ Yuklashni yakunlash ({pages_count} ta sahifa)",
                callback_data="admin_finish_chapter",
                style="success"
            )
        )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_admin_after_chapter_keyboard(manga_id: int, next_ch: int) -> InlineKeyboardMarkup:
    """Bob yuklangandan so'ng keyingi bobni tezkor yuklash tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"➕ Keyingi {next_ch}-bobni yuklash",
            callback_data=f"quick_add_ch_{manga_id}_{next_ch}",
            style="success"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📑 Boshqa manga tanlash", callback_data="admin_add_chapter", style="primary"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home", style="primary")
    )
    return builder.as_markup()



def get_animes_list_keyboard(animes: List[Dict[str, Any]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Animelar ro'yxatini sahifalash va boshqarish tugmalari"""
    builder = InlineKeyboardBuilder()
    for a in animes:
        ep_info = f"({a.get('uploaded_episodes', 0)} qism)"
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 [{a['id']}] {a['title'][:22]} {ep_info}",
                callback_data=f"admin_manage_anime_{a['id']}",
                style="primary"
            )
        )

    # Navigatsiya
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin_list_animes_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{max(total_pages, 1)}", callback_data="ignore"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin_list_animes_{page+1}"))
    builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="➕ Yangi anime qo'shish", callback_data="admin_add_anime", style="success"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_home")
    )
    return builder.as_markup()


def get_anime_manage_keyboard(anime_id: int, next_ep: int) -> InlineKeyboardMarkup:
    """Bitta animeni boshqarish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🎬 {next_ep}-qismni yuklash",
            callback_data=f"quick_add_ep_{anime_id}_{next_ep}",
            style="success"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📢 Kanalga postlash", callback_data=f"repost_{anime_id}", style="primary"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"confirm_del_anime_{anime_id}", style="danger")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Animelar ro'yxatiga qaytish", callback_data="admin_list_animes_0")
    )
    return builder.as_markup()


def get_delete_confirm_keyboard(anime_id: int) -> InlineKeyboardMarkup:
    """Animeni o'chirishni tasdiqlash tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirilsin", callback_data=f"confirm_del_anime_{anime_id}", style="danger"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="primary")
    )
    return builder.as_markup()


def get_admin_cancel_keyboard() -> InlineKeyboardMarkup:
    """Bekor qilish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel", style="danger")
    )
    return builder.as_markup()


def get_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Kabinet ichidagi tugmalar"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 VIP sotib olish", callback_data="btn_vip"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="btn_cabinet")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home")
    )
    return builder.as_markup()


def get_back_home_keyboard() -> InlineKeyboardMarkup:
    """Faqat bosh menyuga qaytish tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="btn_home", style="primary")
    )
    return builder.as_markup()


def get_vip_plans_keyboard() -> InlineKeyboardMarkup:
    """VIP tariflarini tanlash tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 𝟭 𝗼𝘆𝗹𝗶𝗸 — 𝟭𝟱,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_1", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="💎 𝟯 𝗼𝘆𝗹𝗶𝗸 — 𝟱𝟬,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_3", style="primary")
    )
    builder.row(
        InlineKeyboardButton(text="👑 𝗗𝗼𝗶𝗺𝗶𝘆 (𝗰𝗵𝗲𝗸𝘀𝗶𝘇) — 𝟭𝟬𝟬,𝟬𝟬𝟬 𝘀𝗼'𝗺", callback_data="buy_vip_unlimited", style="success")
    )
    builder.row(
        InlineKeyboardButton(text="👨🏻‍💻 𝗔𝗱𝗺𝗶𝗻 𝗯𝗶𝗹𝗮𝗻 𝗯𝗼𝗴'𝗹𝗮𝗻𝗶𝘀𝗵", url="https://t.me/Jahongir02_02")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ 𝗕𝗼𝘀𝗵 𝗺𝗲𝗻𝘆𝘂", callback_data="btn_home")
    )
    return builder.as_markup()


def get_vip_payment_keyboard(plan_id: str, user_id: int) -> InlineKeyboardMarkup:
    """To'lov qilish va chek yuborish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 𝗖𝗵𝗲𝗸 (𝘀𝗸𝗿𝗶𝗻𝘀𝗵𝗼𝘁) 𝘆𝘂𝗯𝗼𝗿𝗶𝘀𝗵", callback_data=f"send_receipt_{plan_id}", style="success")
    )
    builder.row(
        InlineKeyboardButton(
            text="👨🏻‍💻 𝗔𝗱𝗺𝗶𝗻𝗴𝗮 𝘆𝗼𝘇𝗶𝘀𝗵",
            url=f"https://t.me/Jahongir02_02"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ 𝗕𝗼𝘀𝗵𝗾𝗮 𝘁𝗮𝗿𝗶𝗳 𝘁𝗮𝗻𝗹𝗮𝘀𝗵", callback_data="btn_vip")
    )
    return builder.as_markup()


def get_admin_vip_approval_keyboard(user_id: int, days: int) -> InlineKeyboardMarkup:
    """Admin uchun chekni tasdiqlash yoki rad etish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash (VIP berish)", callback_data=f"approve_vip_{user_id}_{days}", style="success"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_vip_{user_id}", style="danger")
    )
    return builder.as_markup()
