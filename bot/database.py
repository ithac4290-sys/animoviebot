import json
import logging
import asyncpg
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bot.config import config

logger = logging.getLogger("Database")


class Database:
    def __init__(self, db_url: Optional[str] = None, sqlite_path: str = "anime_bot.db"):
        self.db_url = db_url or config.database_url
        self.sqlite_path = sqlite_path
        self.pool: Optional[asyncpg.Pool] = None
        self.is_postgres = bool(self.db_url and "postgres" in self.db_url)

    async def init_db(self):
        """Ma'lumotlar bazasiga ulanish va jadvallarni initsializatsiya qilish"""
        if self.is_postgres:
            try:
                # asyncpg uchun URL tozalash
                clean_url = self.db_url.split("?")[0]
                self.pool = await asyncpg.create_pool(
                    clean_url,
                    ssl="require",
                    min_size=1,
                    max_size=10
                )
                logger.info("Neon PostgreSQL ulanishlar puli (Pool) muvaffaqiyatli yaratildi!")
                await self._init_postgres_tables()
                return
            except Exception as e:
                logger.error(f"PostgreSQL ga ulanishda xatolik: {e}. SQLite zaxira rejimiga o'tilmoqda.")
                self.is_postgres = False

        # Zaxira SQLite rejimi
        await self._init_sqlite_tables()

    async def _init_postgres_tables(self):
        """PostgreSQL jadvallarini yaratish (JSONB qo'llab-quvvatlashi bilan)"""
        async with self.pool.acquire() as conn:
            # 1. Foydalanuvchilar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    vip_until TEXT,
                    data JSONB DEFAULT '{}'::jsonb,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Animelar jadvali (barcha video va qismlar data JSONB ustunida saqlanadi)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS animes (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    poster TEXT NOT NULL,
                    status TEXT NOT NULL,
                    episodes_count TEXT NOT NULL,
                    genres TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    views INTEGER DEFAULT 0,
                    data JSONB DEFAULT '{"episodes": {}}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Qismlar jadvali (har bir video va uning metama'lumotlari JSONB da saqlanadi)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id SERIAL PRIMARY KEY,
                    anime_id INTEGER NOT NULL REFERENCES animes(id) ON DELETE CASCADE,
                    episode_num INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    caption TEXT,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(anime_id, episode_num)
                );
            """)

            # 4. Sponsor kanallar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_channels (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    invite_link TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    data JSONB DEFAULT '{}'::jsonb
                );
            """)

            # 5. Mangalar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS mangas (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    cover TEXT NOT NULL,
                    genre TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chapters_count INTEGER DEFAULT 1,
                    description TEXT,
                    rating TEXT DEFAULT '4.9',
                    data JSONB DEFAULT '{"chapters": []}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 6. Shorts jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shorts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    video_file_id TEXT NOT NULL,
                    video_url TEXT,
                    creator TEXT DEFAULT '@Ani_Movei_UZ',
                    caption TEXT,
                    sound_title TEXT DEFAULT 'AniMovie Asl ovoz',
                    likes_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. TezCheck To'lovlar jadvali (Click, Payme, Uzum orqali avtomat to'lovlar)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tezcheck_payments (
                    id SERIAL PRIMARY KEY,
                    bill_id TEXT UNIQUE NOT NULL,
                    user_id BIGINT NOT NULL,
                    plan_key TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    amount_uzs INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    payment_url TEXT,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 8. Telegram Business Chatbot ulanishlari jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS business_connections (
                    connection_id TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_chat_id BIGINT NOT NULL,
                    can_reply INTEGER DEFAULT 1,
                    is_enabled INTEGER DEFAULT 1,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 9. Faol 1-ga-1 Business chatlar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS business_chats (
                    user_id BIGINT PRIMARY KEY,
                    connection_id TEXT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 10. Homiy botlar jadvali (PostgreSQL)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_bots (
                    id SERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    bot_token TEXT UNIQUE NOT NULL,
                    bot_id BIGINT NOT NULL,
                    bot_username TEXT NOT NULL,
                    bot_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("PostgreSQL jadvallari tekshirildi va tayyor!")

    async def _init_sqlite_tables(self):
        """SQLite zaxira jadvallari"""
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    vip_until TEXT,
                    data TEXT DEFAULT '{}',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS animes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    poster TEXT NOT NULL,
                    status TEXT NOT NULL,
                    episodes_count TEXT NOT NULL,
                    genres TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    views INTEGER DEFAULT 0,
                    data TEXT DEFAULT '{"episodes": {}}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id INTEGER NOT NULL,
                    episode_num INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    caption TEXT,
                    data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(anime_id, episode_num)
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    invite_link TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mangas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    cover TEXT NOT NULL,
                    genre TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chapters_count INTEGER DEFAULT 1,
                    description TEXT,
                    rating TEXT DEFAULT '4.9',
                    data TEXT DEFAULT '{"chapters": []}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS shorts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    video_file_id TEXT NOT NULL,
                    video_url TEXT,
                    creator TEXT DEFAULT '@Ani_Movei_UZ',
                    caption TEXT,
                    sound_title TEXT DEFAULT 'AniMovie Asl ovoz',
                    likes_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. TezCheck To'lovlar jadvali (SQLite)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tezcheck_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    plan_key TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    amount_uzs INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    payment_url TEXT,
                    data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS business_connections (
                    connection_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    user_chat_id INTEGER NOT NULL,
                    can_reply INTEGER DEFAULT 1,
                    is_enabled INTEGER DEFAULT 1,
                    data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS business_chats (
                    user_id INTEGER PRIMARY KEY,
                    connection_id TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 10. Homiy botlar jadvali (SQLite)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    bot_token TEXT UNIQUE NOT NULL,
                    bot_id INTEGER NOT NULL,
                    bot_username TEXT NOT NULL,
                    bot_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

    # ================= Foydalanuvchilar bilan ishlash =================

    async def add_or_update_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        """Foydalanuvchini bazaga qo'shish yoki yangilash"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO users (user_id, full_name, username)
                    VALUES ($1, $2, $3)
                    ON CONFLICT(user_id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        username = EXCLUDED.username;
                """, user_id, full_name, username)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO users (user_id, full_name, username)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        full_name = excluded.full_name,
                        username = excluded.username
                """, (user_id, full_name, username))
                await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi ma'lumotlarini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                return dict(row) if row else None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_users(self) -> List[int]:
        """Barcha foydalanuvchilar ID ro'yxatini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT user_id FROM users")
                return [r["user_id"] for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT user_id FROM users")
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def get_users_count(self) -> int:
        """Foydalanuvchilar soni"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT COUNT(*) FROM users")
                return val or 0
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_vip_users_count(self) -> int:
        """VIP foydalanuvchilar soni"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_vip = 1")
                return val or 0
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1")
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def give_vip(self, user_id: int, days: int) -> bool:
        """Foydalanuvchiga VIP berish"""
        user = await self.get_user(user_id)
        if not user:
            return False

        now = datetime.now()
        if user.get("is_vip") and user.get("vip_until"):
            try:
                current_until = datetime.fromisoformat(user["vip_until"])
                new_until = (current_until if current_until > now else now) + timedelta(days=days)
            except Exception:
                new_until = now + timedelta(days=days)
        else:
            new_until = now + timedelta(days=days)

        new_until_str = new_until.isoformat()

        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users
                    SET is_vip = 1, vip_until = $1
                    WHERE user_id = $2;
                """, new_until_str, user_id)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    UPDATE users
                    SET is_vip = 1, vip_until = ?
                    WHERE user_id = ?
                """, (new_until_str, user_id))
                await db.commit()
                return True

    async def check_user_vip_status(self, user_id: int) -> bool:
        """VIP holatini tekshirish"""
        user = await self.get_user(user_id)
        if not user or not user.get("is_vip"):
            return False

        vip_until = user.get("vip_until")
        if not vip_until:
            return False

        try:
            until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() <= until_dt:
                return True
            else:
                if self.is_postgres and self.pool:
                    async with self.pool.acquire() as conn:
                        await conn.execute("UPDATE users SET is_vip = 0 WHERE user_id = $1", user_id)
                else:
                    async with aiosqlite.connect(self.sqlite_path) as db:
                        await db.execute("UPDATE users SET is_vip = 0 WHERE user_id = ?", (user_id,))
                        await db.commit()
                return False
        except Exception:
            return False

    # ================= TezCheck To'lovlari bilan ishlash =================

    async def create_tezcheck_payment(
        self,
        bill_id: str,
        user_id: int,
        plan_key: str,
        days: int,
        amount_uzs: int,
        payment_url: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Yangi TezCheck to'lov yozuvini yaratish"""
        data_json = json.dumps(data or {})
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO tezcheck_payments (bill_id, user_id, plan_key, days, amount_uzs, payment_url, data, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'pending')
                    ON CONFLICT (bill_id) DO UPDATE SET
                        status = 'pending',
                        payment_url = EXCLUDED.payment_url,
                        data = EXCLUDED.data;
                """, bill_id, user_id, plan_key, days, amount_uzs, payment_url, data_json)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO tezcheck_payments (bill_id, user_id, plan_key, days, amount_uzs, payment_url, data, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (bill_id, user_id, plan_key, days, amount_uzs, payment_url, data_json))
                await db.commit()
                return True

    async def get_tezcheck_payment(self, bill_id: str) -> Optional[Dict[str, Any]]:
        """Bill ID orqali TezCheck to'lovini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM tezcheck_payments WHERE bill_id = $1", bill_id)
                if not row:
                    return None
                res = dict(row)
                if isinstance(res.get("data"), str):
                    try:
                        res["data"] = json.loads(res["data"])
                    except Exception:
                        res["data"] = {}
                return res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM tezcheck_payments WHERE bill_id = ?", (bill_id,))
                row = await cursor.fetchone()
                if not row:
                    return None
                res = dict(row)
                if isinstance(res.get("data"), str):
                    try:
                        res["data"] = json.loads(res["data"])
                    except Exception:
                        res["data"] = {}
                return res

    async def update_tezcheck_payment_status(self, bill_id: str, status: str) -> bool:
        """To'lov holatini yangilash ('paid', 'expired', 'canceled')"""
        now_str = datetime.now().isoformat()
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                res = await conn.execute("""
                    UPDATE tezcheck_payments
                    SET status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE bill_id = $2
                """, status, bill_id)
                return "UPDATE" in res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("""
                    UPDATE tezcheck_payments
                    SET status = ?, updated_at = ?
                    WHERE bill_id = ?
                """, (status, now_str, bill_id))
                await db.commit()
                return cursor.rowcount > 0

    # ================= Animelar bilan ishlash =================

    async def add_anime(self, title: str, poster: str, status: str, episodes_count: str,
                        genres: str, channel: str, poster_hash: Optional[str] = None,
                        poster_unique_id: Optional[str] = None,
                        alt_titles: Optional[List[str]] = None) -> int:
        """
        Yangi anime qo'shish va uning noyob ID sini qaytarish.
        Barcha ma'lumotlar, rasm posteri hashlari data JSONB maydonida ham struktura qilib saqlanadi!
        """
        initial_data = json.dumps({
            "title": title,
            "status": status,
            "episodes_count": episodes_count,
            "genres": genres,
            "channel": channel,
            "poster_hash": poster_hash,
            "poster_unique_id": poster_unique_id,
            "alt_titles": alt_titles or [],
            "episodes": {}
        })

        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                anime_id = await conn.fetchval("""
                    INSERT INTO animes (title, poster, status, episodes_count, genres, channel, data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    RETURNING id;
                """, title, poster, status, episodes_count, genres, channel, initial_data)
                return anime_id
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("""
                    INSERT INTO animes (title, poster, status, episodes_count, genres, channel, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, poster, status, episodes_count, genres, channel, initial_data))
                await db.commit()
                return cursor.lastrowid

    @staticmethod
    def _parse_anime_dict(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not d:
            return d
        res = dict(d)
        data = res.get("data")
        if isinstance(data, str):
            try:
                res["data"] = json.loads(data)
            except Exception:
                res["data"] = {}
        elif not isinstance(data, dict):
            res["data"] = {}
        return res

    async def get_anime(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Anime ma'lumotlarini ID orqali olish (barcha JSON videolari bilan birga)"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM animes WHERE id = $1", anime_id)
                if row:
                    return self._parse_anime_dict(dict(row))
                return None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM animes WHERE id = ?", (anime_id,))
                row = await cursor.fetchone()
                if row:
                    return self._parse_anime_dict(dict(row))
                return None

    get_anime_by_id = get_anime

    async def increment_anime_views(self, anime_id: int):
        """Ko'rishlar sonini oshirish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE animes SET views = views + 1 WHERE id = $1", anime_id)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,))
                await db.commit()

    async def search_animes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Qidiruv (nomi va data JSON dagi boshqa muqobil nomlar bo'yicha)"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                if query.isdigit():
                    rows = await conn.fetch("SELECT * FROM animes WHERE id = $1", int(query))
                else:
                    search_term = f"%{query}%"
                    rows = await conn.fetch("""
                        SELECT * FROM animes
                        WHERE title ILIKE $1 OR (data::text) ILIKE $1
                        ORDER BY views DESC, id DESC
                        LIMIT $2
                    """, search_term, limit)
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                if query.isdigit():
                    cursor = await db.execute("SELECT * FROM animes WHERE id = ?", (int(query),))
                else:
                    search_term = f"%{query}%"
                    cursor = await db.execute(
                        "SELECT * FROM animes WHERE title LIKE ? OR data LIKE ? ORDER BY views DESC LIMIT ?",
                        (search_term, search_term, limit)
                    )
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def get_all_anime_posters(self) -> List[Dict[str, Any]]:
        """Barcha animelarning rasm posterlari va hashlarini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id, title, poster, data FROM animes")
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT id, title, poster, data FROM animes")
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def update_anime_poster_hash(self, anime_id: int, poster_hash: str,
                                       poster_unique_id: Optional[str] = None,
                                       alt_titles: Optional[List[str]] = None):
        """Anime uchun rasm dHash va muqobil nomlarni bazaga saqlash"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT data FROM animes WHERE id = $1", anime_id)
                current_data = {}
                if row and row["data"]:
                    current_data = json.loads(row["data"]) if isinstance(row["data"], str) else dict(row["data"])
                current_data["poster_hash"] = poster_hash
                if poster_unique_id:
                    current_data["poster_unique_id"] = poster_unique_id
                if alt_titles:
                    existing_alts = current_data.get("alt_titles", [])
                    for at in alt_titles:
                        if at and at not in existing_alts:
                            existing_alts.append(at)
                    current_data["alt_titles"] = existing_alts
                await conn.execute("UPDATE animes SET data = $1::jsonb WHERE id = $2", json.dumps(current_data), anime_id)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT data FROM animes WHERE id = ?", (anime_id,))
                row = await cursor.fetchone()
                current_data = {}
                if row and row[0]:
                    try:
                        current_data = json.loads(row[0])
                    except Exception:
                        pass
                current_data["poster_hash"] = poster_hash
                if poster_unique_id:
                    current_data["poster_unique_id"] = poster_unique_id
                if alt_titles:
                    existing_alts = current_data.get("alt_titles", [])
                    for at in alt_titles:
                        if at and at not in existing_alts:
                            existing_alts.append(at)
                    current_data["alt_titles"] = existing_alts
                await db.execute("UPDATE animes SET data = ? WHERE id = ?", (json.dumps(current_data), anime_id))
                await db.commit()

    async def get_top_animes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """TOP animelar"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM animes
                    ORDER BY views DESC, id DESC
                    LIMIT $1
                """, limit)
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM animes ORDER BY views DESC, id DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def get_latest_animes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """So'ngi yuklangan animelar"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM animes
                    ORDER BY id DESC
                    LIMIT $1
                """, limit)
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM animes ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def search_animes_by_genre(self, genre: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Janr bo'yicha qidirish"""
        search_term = f"%{genre}%"
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM animes
                    WHERE genres ILIKE $1
                    ORDER BY views DESC, id DESC
                    LIMIT $2
                """, search_term, limit)
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM animes WHERE genres LIKE ? ORDER BY views DESC, id DESC LIMIT ?",
                    (search_term, limit)
                )
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def get_animes_count(self) -> int:
        """Jami animelar soni"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT COUNT(*) FROM animes")
                return val or 0
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM animes")
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_total_views(self) -> int:
        """Barcha animelarning umumiy ko'rishlar soni"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT COALESCE(SUM(views), 0) FROM animes")
                return int(val or 0)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COALESCE(SUM(views), 0) FROM animes")
                row = await cursor.fetchone()
                return int(row[0] or 0) if row else 0

    async def get_animes_paginated(self, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """Admin ro'yxati uchun animelarni sahifalab olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT a.*, 
                           COALESCE((SELECT COUNT(*) FROM episodes e WHERE e.anime_id = a.id), 0) as uploaded_episodes
                    FROM animes a
                    ORDER BY a.id DESC
                    LIMIT $1 OFFSET $2
                """, limit, offset)
                return [self._parse_anime_dict(dict(r)) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT a.*, 
                           COALESCE((SELECT COUNT(*) FROM episodes e WHERE e.anime_id = a.id), 0) as uploaded_episodes
                    FROM animes a
                    ORDER BY a.id DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                rows = await cursor.fetchall()
                return [self._parse_anime_dict(dict(r)) for r in rows]

    async def delete_anime(self, anime_id: int) -> bool:
        """Animeni o'chirish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM episodes WHERE anime_id = $1", anime_id)
                res = await conn.execute("DELETE FROM animes WHERE id = $1", anime_id)
                return "DELETE 1" in res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("DELETE FROM episodes WHERE anime_id = ?", (anime_id,))
                cursor = await db.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
                await db.commit()
                return cursor.rowcount > 0

    # ================= Qismlar (Videolar) bilan ishlash (JSON Formatda) =================

    async def add_episode(self, anime_id: int, episode_num: int, file_id: str,
                          file_type: str = "video", caption: Optional[str] = None):
        """
        Anime qismini qo'shish.
        Barcha video ma'lumotlari, ID lar va tafsilotlar JSON formatda data maydoniga saqlanadi!
        """
        episode_json_data = {
            "anime_id": anime_id,
            "episode_num": episode_num,
            "file_id": file_id,
            "file_type": file_type,
            "caption": caption,
            "created_at": datetime.now().isoformat()
        }
        episode_json_str = json.dumps(episode_json_data)

        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                # 1. episodes jadvaliga yozish
                await conn.execute("""
                    INSERT INTO episodes (anime_id, episode_num, file_id, file_type, caption, data)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    ON CONFLICT(anime_id, episode_num) DO UPDATE SET
                        file_id = EXCLUDED.file_id,
                        file_type = EXCLUDED.file_type,
                        caption = EXCLUDED.caption,
                        data = EXCLUDED.data;
                """, anime_id, episode_num, file_id, file_type, caption, episode_json_str)

                # 2. animes jadvalidagi data JSONB maydoniga ushbu qismni to'liq saqlash!
                await conn.execute("""
                    UPDATE animes
                    SET data = jsonb_set(
                        COALESCE(data, '{"episodes": {}}'::jsonb),
                        ARRAY['episodes', $2::text],
                        $3::jsonb
                    )
                    WHERE id = $1;
                """, anime_id, str(episode_num), episode_json_str)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO episodes (anime_id, episode_num, file_id, file_type, caption, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(anime_id, episode_num) DO UPDATE SET
                        file_id = excluded.file_id,
                        file_type = excluded.file_type,
                        caption = excluded.caption,
                        data = excluded.data
                """, (anime_id, episode_num, file_id, file_type, caption, episode_json_str))
                await db.commit()

    async def get_episode(self, anime_id: int, episode_num: int) -> Optional[Dict[str, Any]]:
        """Aniq qismni olish (JSON ma'lumotlari bilan)"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM episodes WHERE anime_id = $1 AND episode_num = $2",
                    anime_id, episode_num
                )
                if row:
                    res = dict(row)
                    if isinstance(res.get("data"), str):
                        try:
                            res["data"] = json.loads(res["data"])
                        except Exception:
                            pass
                    return res
                return None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM episodes WHERE anime_id = ? AND episode_num = ?",
                    (anime_id, episode_num)
                )
                row = await cursor.fetchone()
                if row:
                    res = dict(row)
                    if isinstance(res.get("data"), str):
                        try:
                            res["data"] = json.loads(res["data"])
                        except Exception:
                            pass
                    return res
                return None

    async def get_anime_episodes(self, anime_id: int) -> List[Dict[str, Any]]:
        """Animening barcha yuklangan qismlarini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM episodes WHERE anime_id = $1 ORDER BY episode_num ASC",
                    anime_id
                )
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM episodes WHERE anime_id = ? ORDER BY episode_num ASC",
                    (anime_id,)
                )
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_episodes_count(self) -> int:
        """Yuklangan qismlar soni"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                val = await conn.fetchval("SELECT COUNT(*) FROM episodes")
                return val or 0
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM episodes")
                row = await cursor.fetchone()
                return row[0] if row else 0

    # ================= Majburiy obuna sponsor kanallari =================

    async def add_sponsor_channel(self, channel_id: str, title: str, invite_link: str) -> bool:
        """Sponsor kanal qo'shish"""
        ch_data = json.dumps({"channel_id": channel_id, "title": title, "invite_link": invite_link})
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sponsor_channels (channel_id, title, invite_link, is_active, data)
                    VALUES ($1, $2, $3, 1, $4::jsonb)
                    ON CONFLICT(channel_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        invite_link = EXCLUDED.invite_link,
                        is_active = 1,
                        data = EXCLUDED.data;
                """, channel_id, title, invite_link, ch_data)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO sponsor_channels (channel_id, title, invite_link, is_active)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(channel_id) DO UPDATE SET
                        title = excluded.title,
                        invite_link = excluded.invite_link,
                        is_active = 1
                """, (channel_id, title, invite_link))
                await db.commit()
                return True

    async def get_active_sponsor_channels(self) -> List[Dict[str, Any]]:
        """Faol sponsor kanallar"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM sponsor_channels WHERE is_active = 1")
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sponsor_channels WHERE is_active = 1")
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_all_sponsor_channels(self) -> List[Dict[str, Any]]:
        """Barcha sponsor kanallar"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM sponsor_channels")
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sponsor_channels")
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def delete_sponsor_channel(self, channel_id: str) -> bool:
        """Kanalni o'chirish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                res = await conn.execute("DELETE FROM sponsor_channels WHERE channel_id = $1", channel_id)
                return "DELETE 1" in res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("DELETE FROM sponsor_channels WHERE channel_id = ?", (channel_id,))
                await db.commit()
                return cursor.rowcount > 0

    # ================= Manga bilan ishlash =================

    async def add_manga(self, title: str, cover: str, genre: str, status: str,
                        chapters_count: int = 1, description: str = "",
                        rating: str = "4.9", data: Optional[Dict[str, Any]] = None) -> int:
        """
        Yangi manga qo'shish.
        Barcha metama'lumotlar to'liq data JSONB maydoniga yuklanadi!
        """
        now_iso = datetime.now().isoformat()
        full_data = {
            "title": title,
            "cover": cover,
            "genre": genre,
            "status": status,
            "chapters_count": chapters_count,
            "description": description,
            "rating": rating,
            "views": 0,
            "likes": 0,
            "chapters": [],
            "created_at": now_iso
        }
        if data and isinstance(data, dict):
            full_data.update(data)

        data_json = json.dumps(full_data)
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                m_id = await conn.fetchval("""
                    INSERT INTO mangas (title, cover, genre, status, chapters_count, description, rating, data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                    RETURNING id;
                """, title, cover, genre, status, chapters_count, description, rating, data_json)
                return m_id
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("""
                    INSERT INTO mangas (title, cover, genre, status, chapters_count, description, rating, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, cover, genre, status, chapters_count, description, rating, data_json))
                await db.commit()
                return cursor.lastrowid

    async def get_all_mangas(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Barcha mangalar ro'yxati"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM mangas ORDER BY id DESC LIMIT $1", limit)
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM mangas ORDER BY id DESC LIMIT ?", (limit,))
                rows = await cursor.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res

    async def get_manga(self, manga_id: int) -> Optional[Dict[str, Any]]:
        """Alohida manga ma'lumotlari"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM mangas WHERE id = $1", manga_id)
                if row:
                    d = dict(row)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    return d
                return None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM mangas WHERE id = ?", (manga_id,))
                row = await cursor.fetchone()
                if row:
                    d = dict(row)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    return d
                return None

    async def add_manga_chapter(self, manga_id: int, chapter_num: int, pages: List[str],
                                title: Optional[str] = None) -> bool:
        """
        Manga uchun yangi bob (sahifalar) yuklash.
        data JSONB maydonidagi chapters ro'yxatini va sahifalarni yangilaydi.
        """
        now_iso = datetime.now().isoformat()
        manga = await self.get_manga(manga_id)
        if not manga:
            return False

        m_data = manga.get("data") or {}
        if isinstance(m_data, str):
            try:
                m_data = json.loads(m_data)
            except Exception:
                m_data = {}

        chapters = m_data.get("chapters", [])
        if not isinstance(chapters, list):
            chapters = []

        new_chapter = {
            "chapter_num": chapter_num,
            "title": title or f"{chapter_num}-bob",
            "pages": pages,
            "pages_count": len(pages),
            "created_at": now_iso
        }

        # Mavjud bob bo'lsa yangilash, bo'lmasa qo'shish
        updated = False
        for idx, ch in enumerate(chapters):
            if isinstance(ch, dict) and ch.get("chapter_num") == chapter_num:
                chapters[idx] = new_chapter
                updated = True
                break

        if not updated:
            chapters.append(new_chapter)

        chapters.sort(key=lambda x: x.get("chapter_num", 0))
        m_data["chapters"] = chapters

        # Yangi boblar soni
        max_ch = max([ch.get("chapter_num", 0) for ch in chapters] + [manga.get("chapters_count", 0), chapter_num])
        m_data["chapters_count"] = max_ch

        data_json = json.dumps(m_data)

        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE mangas
                    SET chapters_count = $1, data = $2::jsonb
                    WHERE id = $3;
                """, max_ch, data_json, manga_id)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    UPDATE mangas
                    SET chapters_count = ?, data = ?
                    WHERE id = ?;
                """, (max_ch, data_json, manga_id))
                await db.commit()
                return True

    async def get_manga_chapters(self, manga_id: int) -> List[Dict[str, Any]]:
        """Manga boblari ro'yxatini olish"""
        manga = await self.get_manga(manga_id)
        if not manga:
            return []
        m_data = manga.get("data") or {}
        return m_data.get("chapters", [])

    async def delete_manga(self, manga_id: int) -> bool:
        """Mangani butunlay o'chirish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                res = await conn.execute("DELETE FROM mangas WHERE id = $1", manga_id)
                return "DELETE 1" in res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("DELETE FROM mangas WHERE id = ?", (manga_id,))
                await db.commit()
                return cursor.rowcount > 0

    async def delete_manga_chapter(self, manga_id: int, chapter_num: int) -> bool:
        """Manganing ma'lum bir bobini o'chirish"""
        manga = await self.get_manga(manga_id)
        if not manga:
            return False

        m_data = manga.get("data") or {}
        if isinstance(m_data, str):
            try:
                m_data = json.loads(m_data)
            except Exception:
                m_data = {}

        chapters = m_data.get("chapters", [])
        if not isinstance(chapters, list):
            return False

        new_chapters = [ch for ch in chapters if isinstance(ch, dict) and ch.get("chapter_num") != chapter_num]
        if len(new_chapters) == len(chapters):
            return False

        m_data["chapters"] = new_chapters
        max_ch = max([ch.get("chapter_num", 0) for ch in new_chapters], default=0)
        m_data["chapters_count"] = max_ch

        data_json = json.dumps(m_data)

        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE mangas
                    SET chapters_count = $1, data = $2::jsonb
                    WHERE id = $3;
                """, max_ch, data_json, manga_id)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    UPDATE mangas
                    SET chapters_count = ?, data = ?
                    WHERE id = ?;
                """, (max_ch, data_json, manga_id))
                await db.commit()
                return True


    # ================= Shorts bilan ishlash =================

    async def add_short(self, title: str, video_file_id: str, video_url: Optional[str] = None,
                        caption: str = "", sound_title: str = "AniMovie Asl ovoz",
                        creator: str = "@Ani_Movei_UZ", data: Optional[Dict[str, Any]] = None) -> int:
        """
        Yangi short video qo'shish.
        Barcha video metama'lumotlari to'liq data JSONB maydoniga yuklanadi!
        """
        now_iso = datetime.now().isoformat()
        full_data = {
            "title": title,
            "video_file_id": video_file_id,
            "video_url": video_url or "",
            "caption": caption,
            "sound_title": sound_title,
            "creator": creator,
            "likes_count": 0,
            "comments_count": 0,
            "views": 0,
            "created_at": now_iso
        }
        if data and isinstance(data, dict):
            full_data.update(data)

        data_json = json.dumps(full_data)
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                s_id = await conn.fetchval("""
                    INSERT INTO shorts (title, video_file_id, video_url, caption, sound_title, creator, data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    RETURNING id;
                """, title, video_file_id, video_url or "", caption, sound_title, creator, data_json)
                return s_id
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("""
                    INSERT INTO shorts (title, video_file_id, video_url, caption, sound_title, creator, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, video_file_id, video_url or "", caption, sound_title, creator, data_json))
                await db.commit()
                return cursor.lastrowid

    async def get_all_shorts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Barcha shortslar ro'yxati"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM shorts ORDER BY id DESC LIMIT $1", limit)
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM shorts ORDER BY id DESC LIMIT ?", (limit,))
                rows = await cursor.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res

    # ================= Telegram Business Chatbot =================

    async def save_business_connection(self, connection_id: str, user_id: int, user_chat_id: int,
                                       can_reply: bool = True, is_enabled: bool = True,
                                       data: Optional[Dict[str, Any]] = None):
        """Telegram Business ulanishini saqlash yoki yangilash"""
        data_json = json.dumps(data or {})
        can_r = 1 if can_reply else 0
        is_en = 1 if is_enabled else 0
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO business_connections (connection_id, user_id, user_chat_id, can_reply, is_enabled, data, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT(connection_id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        user_chat_id = EXCLUDED.user_chat_id,
                        can_reply = EXCLUDED.can_reply,
                        is_enabled = EXCLUDED.is_enabled,
                        data = EXCLUDED.data,
                        updated_at = CURRENT_TIMESTAMP;
                """, connection_id, user_id, user_chat_id, can_r, is_en, data_json)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO business_connections (connection_id, user_id, user_chat_id, can_reply, is_enabled, data, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(connection_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        user_chat_id = excluded.user_chat_id,
                        can_reply = excluded.can_reply,
                        is_enabled = excluded.is_enabled,
                        data = excluded.data,
                        updated_at = CURRENT_TIMESTAMP;
                """, (connection_id, user_id, user_chat_id, can_r, is_en, data_json))
                await db.commit()

    async def get_business_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Telegram Business ulanishini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM business_connections WHERE connection_id = $1", connection_id)
                if row:
                    d = dict(row)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    return d
                return None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM business_connections WHERE connection_id = ?", (connection_id,))
                row = await cursor.fetchone()
                if row:
                    d = dict(row)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    return d
                return None

    async def record_business_chat(self, user_id: int, connection_id: str, chat_id: int):
        """Oxirgi faol 1-ga-1 business chatini eslab qolish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO business_chats (user_id, connection_id, chat_id, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        connection_id = EXCLUDED.connection_id,
                        chat_id = EXCLUDED.chat_id,
                        updated_at = CURRENT_TIMESTAMP;
                """, user_id, connection_id, chat_id)
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO business_chats (user_id, connection_id, chat_id, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        connection_id = excluded.connection_id,
                        chat_id = excluded.chat_id,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, connection_id, chat_id))
                await db.commit()

    async def get_active_business_chat(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Foydalanuvchining faol 1-ga-1 business chatini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT bc.connection_id, bc.chat_id
                    FROM business_chats bc
                    WHERE bc.user_id = $1
                    ORDER BY bc.updated_at DESC LIMIT 1
                """, user_id)
                return dict(row) if row else None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT bc.connection_id, bc.chat_id
                    FROM business_chats bc
                    WHERE bc.user_id = ?
                    ORDER BY bc.updated_at DESC LIMIT 1
                """, (user_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

    # ================= Homiy botlar (Sponsor Bots) =================

    async def add_sponsor_bot(
        self,
        owner_id: int,
        bot_token: str,
        bot_id: int,
        bot_username: str,
        bot_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Yangi homiy botni saqlash yoki yangilash"""
        data_json = json.dumps(data or {})
        bot_username = bot_username.lstrip("@")
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sponsor_bots (owner_id, bot_token, bot_id, bot_username, bot_name, is_active, data)
                    VALUES ($1, $2, $3, $4, $5, 1, $6::jsonb)
                    ON CONFLICT(bot_token) DO UPDATE SET
                        owner_id = EXCLUDED.owner_id,
                        bot_id = EXCLUDED.bot_id,
                        bot_username = EXCLUDED.bot_username,
                        bot_name = EXCLUDED.bot_name,
                        is_active = 1,
                        data = EXCLUDED.data;
                """, owner_id, bot_token, bot_id, bot_username, bot_name, data_json)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("""
                    INSERT INTO sponsor_bots (owner_id, bot_token, bot_id, bot_username, bot_name, is_active, data)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(bot_token) DO UPDATE SET
                        owner_id = excluded.owner_id,
                        bot_id = excluded.bot_id,
                        bot_username = excluded.bot_username,
                        bot_name = excluded.bot_name,
                        is_active = 1,
                        data = excluded.data
                """, (owner_id, bot_token, bot_id, bot_username, bot_name, data_json))
                await db.commit()
                return True

    async def get_active_sponsor_bots(self) -> List[Dict[str, Any]]:
        """Barcha faol homiy botlarni olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM sponsor_bots WHERE is_active = 1 ORDER BY id ASC")
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sponsor_bots WHERE is_active = 1 ORDER BY id ASC")
                rows = await cursor.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res

    async def get_user_sponsor_bots(self, owner_id: int) -> List[Dict[str, Any]]:
        """Foydalanuvchining barcha homiy botlarini olish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM sponsor_bots WHERE owner_id = $1 ORDER BY id DESC", owner_id)
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sponsor_bots WHERE owner_id = ? ORDER BY id DESC", (owner_id,))
                rows = await cursor.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("data"), str):
                        try:
                            d["data"] = json.loads(d["data"])
                        except Exception:
                            pass
                    res.append(d)
                return res

    async def get_sponsor_bot_by_token(self, bot_token: str) -> Optional[Dict[str, Any]]:
        """Token bo'yicha homiy botni topish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM sponsor_bots WHERE bot_token = $1", bot_token)
                return dict(row) if row else None
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sponsor_bots WHERE bot_token = ?", (bot_token,))
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def delete_sponsor_bot(self, bot_id: int, owner_id: Optional[int] = None) -> bool:
        """Homiy botni o'chirish"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                if owner_id:
                    await conn.execute("DELETE FROM sponsor_bots WHERE bot_id = $1 AND owner_id = $2", bot_id, owner_id)
                else:
                    await conn.execute("DELETE FROM sponsor_bots WHERE bot_id = $1", bot_id)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                if owner_id:
                    await db.execute("DELETE FROM sponsor_bots WHERE bot_id = ? AND owner_id = ?", (bot_id, owner_id))
                else:
                    await db.execute("DELETE FROM sponsor_bots WHERE bot_id = ?", (bot_id,))
                await db.commit()
                return True

    async def set_sponsor_bot_status(self, bot_id: int, is_active: int) -> bool:
        """Homiy bot holatini yangilash (1=faol, 0=to'xtatilgan)"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE sponsor_bots SET is_active = $1 WHERE bot_id = $2", is_active, bot_id)
                return True
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute("UPDATE sponsor_bots SET is_active = ? WHERE bot_id = ?", (is_active, bot_id))
                await db.commit()
                return True


db = Database()
