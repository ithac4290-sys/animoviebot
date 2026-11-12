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

from bot.config import config
from bot.database import db
from bot.handlers import setup_routers
from bot.middlewares import UserRegisterMiddleware


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

    if not config.bot_token or config.bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN ko'rsatilmagan! Iltimos, .env faylini to'ldiring.")
        return

    # 1. Ma'lumotlar bazasini initsializatsiya qilish
    logger.info("Ma'lumotlar bazasi ishga tushirilmoqda...")
    await db.init_db()

    # 2. Xatoliklarga chidamli sessiya yaratish
    session = RetryAiohttpSession(timeout=60.0)

    # 3. Bot va Dispatcher yaratish
    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 4. Middleware ulash
    dp.update.outer_middleware(UserRegisterMiddleware())

    # 5. Handlerlarni ulash
    dp.include_router(setup_routers())

    # Bot ma'lumotlarini olish
    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")

    # 6. Pollingni boshlash
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
