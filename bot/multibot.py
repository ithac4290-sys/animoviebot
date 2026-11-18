import asyncio
import logging
import aiohttp
from typing import Optional, Dict, Any, Tuple
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError, TelegramAPIError

from bot.database import db

logger = logging.getLogger("MultiBotManager")


class RetryAiohttpSession(AiohttpSession):
    """Tarmoq uzilishlariga chidamli sessiya"""
    async def make_request(self, bot, method, timeout=None):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                return await super().make_request(bot, method, timeout=timeout)
            except (TelegramNetworkError, aiohttp.ClientError, asyncio.TimeoutError, ConnectionResetError) as e:
                if attempt == max_retries:
                    raise
                await asyncio.sleep(attempt * 1.5)


class MultiBotManager:
    _main_bot: Optional[Bot] = None
    _dp: Optional[Dispatcher] = None
    _active_bots: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def init(cls, main_bot: Bot, dp: Dispatcher):
        cls._main_bot = main_bot
        cls._dp = dp

    @classmethod
    def get_main_bot(cls) -> Optional[Bot]:
        return cls._main_bot

    @classmethod
    def get_dispatcher(cls) -> Optional[Dispatcher]:
        return cls._dp

    @classmethod
    def is_bot_active(cls, bot_id: int) -> bool:
        return bot_id in cls._active_bots

    @classmethod
    async def start_bot(cls, bot_token: str, owner_id: int = 0) -> Tuple[bool, str, Optional[Any]]:
        """
        Homiy botni tekshirib, ishga tushirish (long-polling rejimida).
        Qaytaradi: (success: bool, message: str, bot_info: User | None)
        """
        bot_token = bot_token.strip()

        # 1. Asosiy bot tokeni bilan bir xilligini tekshirish
        if cls._main_bot and cls._main_bot.token == bot_token:
            return False, "⚠️ Bu asosiy botning tokeni! Iltimos, o'zingizning @BotFather orqali ochilgan bot tokeningizni yuboring.", None

        # 2. Yangi Bot obyektini yaratish
        session = RetryAiohttpSession(timeout=60.0)
        bot = Bot(
            token=bot_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # 3. Tokenni Telegram API orqali tekshirish
        try:
            bot_info = await bot.get_me()
        except TelegramUnauthorizedError:
            await bot.session.close()
            return False, "❌ <b>Token yaroqsiz!</b>\nTelegram serveri ushbu tokenni qabul qilmadi. Iltimos, @BotFather dan to'g'ri nusxa olganingizga ishonch hosil qiling.", None
        except Exception as e:
            await bot.session.close()
            logger.error(f"Bot tokenini tekshirishda xatolik: {e}")
            return False, f"❌ Telegram API bilan ulanishda xatolik yuz berdi: {str(e)}", None

        # 4. Agar bot allaqachon ishlayotgan bo'lsa, avval to'xtatish
        if bot_info.id in cls._active_bots:
            await cls.stop_bot(bot_info.id)

        # 5. Webhookni tozalash
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.warning(f"Homiy bot @{bot_info.username} webhook tozalashda xatolik: {e}")

        # 6. Polling vazifasini yaratish va ishga tushirish
        task = asyncio.create_task(
            cls._poll_bot_loop(bot, bot_info.username or "Bot", bot_info.id)
        )

        cls._active_bots[bot_info.id] = {
            "bot": bot,
            "task": task,
            "username": bot_info.username,
            "name": bot_info.first_name,
            "owner_id": owner_id,
            "token": bot_token
        }

        logger.info(f"✅ Homiy bot ishga tushirildi: @{bot_info.username} (ID: {bot_info.id}, Egasi: {owner_id})")
        return True, "Bot muvaffaqiyatli ishga tushirildi!", bot_info

    @classmethod
    async def _poll_bot_loop(cls, bot: Bot, username: str, bot_id: int):
        """Homiy bot uchun polling sikli"""
        dp = cls._dp
        if not dp:
            logger.error("Dispatcher initsializatsiya qilinmagan!")
            return

        offset = None
        allowed_updates = dp.resolve_used_update_types()

        logger.info(f"Homiy bot @{username} (ID: {bot_id}) uchun polling jarayoni boshlandi.")
        while True:
            try:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=20,
                    allowed_updates=allowed_updates
                )
                for update in updates:
                    offset = update.update_id + 1
                    # Dispatcher ga xabarni yo'naltirish
                    asyncio.create_task(dp.feed_update(bot=bot, update=update))
            except asyncio.CancelledError:
                logger.info(f"Homiy bot @{username} polling to'xtatildi (Cancelled).")
                break
            except TelegramUnauthorizedError:
                logger.warning(f"Homiy bot @{username} tokeni bekor qilingan (Unauthorized). To'xtatilmoqda...")
                await db.set_sponsor_bot_status(bot_id, 0)
                cls._active_bots.pop(bot_id, None)
                break
            except (TelegramNetworkError, aiohttp.ClientError, asyncio.TimeoutError, ConnectionResetError) as e:
                await asyncio.sleep(2)
            except Exception as e:
                err_text = str(e).lower()
                if "unauthorized" in err_text or "token is invalid" in err_text:
                    logger.warning(f"Homiy bot @{username} tokeni bekor qilingan ({e}).")
                    await db.set_sponsor_bot_status(bot_id, 0)
                    cls._active_bots.pop(bot_id, None)
                    break
                logger.warning(f"Homiy bot @{username} polling xatoligi: {e}")
                await asyncio.sleep(4)

        try:
            await bot.session.close()
        except Exception:
            pass

    @classmethod
    async def stop_bot(cls, bot_id: int):
        """Homiy botni to'xtatish"""
        info = cls._active_bots.pop(bot_id, None)
        if info:
            task: asyncio.Task = info.get("task")
            bot: Bot = info.get("bot")
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            if bot:
                try:
                    await bot.session.close()
                except Exception:
                    pass
            logger.info(f"Homiy bot to'xtatildi: ID {bot_id}")

    @classmethod
    async def start_all_saved_bots(cls):
        """Bazada saqlangan barcha faol homiy botlarni fonda ishga tushirish"""
        bots = await db.get_active_sponsor_bots()
        if not bots:
            logger.info("Faol homiy botlar topilmadi.")
            return

        logger.info(f"Bazada {len(bots)} ta faol homiy bot topildi. Ishga tushirilmoqda...")
        started_count = 0
        for b in bots:
            token = b.get("bot_token")
            owner_id = b.get("owner_id", 0)
            if not token:
                continue
            success, msg, bot_info = await cls.start_bot(token, owner_id)
            if success:
                started_count += 1
            else:
                logger.warning(f"Homiy bot (ID: {b.get('bot_id')}) ni ishga tushirishda xatolik: {msg}")

        logger.info(f"Jami {started_count}/{len(bots)} ta homiy bot muvaffaqiyatli ishga tushirildi.")

    @classmethod
    async def stop_all(cls):
        """Barcha homiy botlarni to'xtatish"""
        bot_ids = list(cls._active_bots.keys())
        for bid in bot_ids:
            await cls.stop_bot(bid)
        cls._active_bots.clear()
        logger.info("Barcha faol homiy botlar to'xtatildi.")
