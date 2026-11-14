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

    # ================= Animelar bilan ishlash =================

    async def add_anime(self, title: str, poster: str, status: str, episodes_count: str,
                        genres: str, channel: str) -> int:
        """
        Yangi anime qo'shish va uning noyob ID sini qaytarish.
        Barcha ma'lumotlar data JSONB maydonida ham struktura qilib saqlanadi!
        """
        initial_data = json.dumps({
            "title": title,
            "status": status,
            "episodes_count": episodes_count,
            "genres": genres,
            "channel": channel,
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

    async def get_anime(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Anime ma'lumotlarini ID orqali olish (barcha JSON videolari bilan birga)"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM animes WHERE id = $1", anime_id)
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
                cursor = await db.execute("SELECT * FROM animes WHERE id = ?", (anime_id,))
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
        """Qidiruv"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                if query.isdigit():
                    rows = await conn.fetch("SELECT * FROM animes WHERE id = $1", int(query))
                else:
                    search_term = f"%{query}%"
                    rows = await conn.fetch("""
                        SELECT * FROM animes
                        WHERE title ILIKE $1
                        ORDER BY views DESC, id DESC
                        LIMIT $2
                    """, search_term, limit)
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                if query.isdigit():
                    cursor = await db.execute("SELECT * FROM animes WHERE id = ?", (int(query),))
                else:
                    search_term = f"%{query}%"
                    cursor = await db.execute(
                        "SELECT * FROM animes WHERE title LIKE ? ORDER BY views DESC LIMIT ?",
                        (search_term, limit)
                    )
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_top_animes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """TOP animelar"""
        if self.is_postgres and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM animes
                    ORDER BY views DESC, id DESC
                    LIMIT $1
                """, limit)
                return [dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM animes ORDER BY views DESC, id DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

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


db = Database()
