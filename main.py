import sys
from pathlib import Path

# Loyihadagi .venv kutubxonalarini har qanday Python orqali ishga tushganda avtomatik ulash
_base_dir = Path(__file__).parent.resolve()
_venv_pkgs = list(_base_dir.glob(".venv/lib/python*/site-packages"))
if _venv_pkgs and str(_venv_pkgs[0]) not in sys.path:
    sys.path.insert(0, str(_venv_pkgs[0]))

import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiohttp import web

from bot.config import config
from bot.database import db
from bot.handlers import setup_routers
from bot.middlewares import UserRegisterMiddleware


async def start_health_server():
    """Railway yoki Render kabi bulutli xizmatlar uchun foniy healthcheck serveri"""
    import os
    port = os.getenv("PORT")
    if port and port.isdigit():
        async def health_check_handler(request):
            return web.Response(text="Anime Bot is running smoothly on Railway!")

        app = web.Application()
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(port))
        await site.start()
        logging.info(f"Railway Healthcheck serveri ishga tushdi: port {port}")


class RetryAiohttpSession(AiohttpSession):
    """
    Internet sifati past bo'lganda yoki Telegram API ulanishni uzganda (ConnectionResetError)
    avtomatik ravishda so'rovni qayta yuboruvchi mustahkam sessiya.
    """
    async def make_request(self, bot, method, timeout=None):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                return await super().make_request(bot, method, timeout=timeout)
            except (TelegramNetworkError, aiohttp.ClientError, asyncio.TimeoutError, ConnectionResetError) as e:
                logging.warning(
                    f"Telegram API ulanishida vaqtinchalik uzilish ({e}). "
                    f"Qayta urinish: {attempt}/{max_retries}..."
                )
                if attempt == max_retries:
                    raise
                await asyncio.sleep(attempt * 1.5)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger("AnimeBot")

    # 1. Railway yoki bulutli hostinglar uchun healthcheck serverini DARHOL ishga tushirish!
    # Bu Railway da 'Port binding failed' yoki 'CRASHED' holatining oldini oladi.
    await start_health_server()

    # 2. Ma'lumotlar bazasini initsializatsiya qilish (Neon PostgreSQL / JSONB)
    logger.info("Ma'lumotlar bazasi initsializatsiya qilinmoqda...")
    try:
        await db.init_db()
    except Exception as e:
        logger.error(f"Bazaga ulanishda xatolik: {e}")

    if not config.bot_token or config.bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN ko'rsatilmagan! Iltimos, .env faylini to'ldiring.")
        # Railway serveri tirik turishi uchun cheksiz kutish
        while True:
            await asyncio.sleep(3600)

    # 3. Xatoliklarga chidamli sessiya yaratish
    session = RetryAiohttpSession(timeout=60.0)

    # 4. Bot va Dispatcher yaratish
    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 5. Middleware ulash
    dp.update.outer_middleware(UserRegisterMiddleware())

    # 6. Handlerlarni ulash
    dp.include_router(setup_routers())

    # 7. Bot ma'lumotlarini olish va ishga tushirish
    while True:
        try:
            bot_info = await bot.get_me()
            logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
            break
        except Exception as e:
            logger.error(
                f"Telegram serveriga ulanishda xatolik: {e}. "
                f"Iltimos, BOT_TOKEN to'g'riligini tekshiring! 25 soniyadan so'ng qayta uriniladi..."
            )
            await asyncio.sleep(25)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
