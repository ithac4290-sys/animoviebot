import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = "anime_bot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Ma'lumotlar bazasi jadvallarini yaratish"""
        async with aiosqlite.connect(self.db_path) as db:
            # Foydalanuvchilar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    vip_until TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Animelar jadvali
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Qismlar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id INTEGER NOT NULL,
                    episode_num INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    caption TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(anime_id, episode_num),
                    FOREIGN KEY(anime_id) REFERENCES animes(id) ON DELETE CASCADE
                )
            """)

            # Majburiy obuna (Sponsor) kanallar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    invite_link TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Bot sozlamalari
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            await db.commit()

    # ================= Foydalanuvchilar bilan ishlash =================

    async def add_or_update_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        """Foydalanuvchini bazaga qo'shish yoki yangilash"""
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def get_all_users(self) -> List[int]:
        """Barcha foydalanuvchilar ID ro'yxatini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_users_count(self) -> int:
        """Foydalanuvchilar umumiy sonini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def give_vip(self, user_id: int, days: int) -> bool:
        """Foydalanuvchiga VIP berish"""
        async with aiosqlite.connect(self.db_path) as db:
            user = await self.get_user(user_id)
            if not user:
                return False

            now = datetime.now()
            if user.get("is_vip") and user.get("vip_until"):
                try:
                    current_until = datetime.fromisoformat(user["vip_until"])
                    if current_until > now:
                        new_until = current_until + timedelta(days=days)
                    else:
                        new_until = now + timedelta(days=days)
                except Exception:
                    new_until = now + timedelta(days=days)
            else:
                new_until = now + timedelta(days=days)

            await db.execute("""
                UPDATE users
                SET is_vip = 1, vip_until = ?
                WHERE user_id = ?
            """, (new_until.isoformat(), user_id))
            await db.commit()
            return True

    async def check_user_vip_status(self, user_id: int) -> bool:
        """Foydalanuvchi hozirda VIP mi yoki yo'qligini tekshirish"""
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
                # VIP muddati tugagan bo'lsa yangilash
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("UPDATE users SET is_vip = 0 WHERE user_id = ?", (user_id,))
                    await db.commit()
                return False
        except Exception:
            return False

    # ================= Animelar bilan ishlash =================

    async def add_anime(self, title: str, poster: str, status: str, episodes_count: str,
                        genres: str, channel: str) -> int:
        """Yangi anime qo'shish va uning noyob ID sini qaytarish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO animes (title, poster, status, episodes_count, genres, channel)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, poster, status, episodes_count, genres, channel))
            await db.commit()
            return cursor.lastrowid

    async def get_anime(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Anime ma'lumotlarini ID orqali olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM animes WHERE id = ?", (anime_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def increment_anime_views(self, anime_id: int):
        """Anime ko'rishlar sonini 1 taga oshirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,))
            await db.commit()

    async def search_animes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Nom yoki ID bo'yicha animelarni qidirish"""
        async with aiosqlite.connect(self.db_path) as db:
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
            return [dict(row) for row in rows]

    async def get_top_animes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Eng ko'p ko'rilgan top animelarni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM animes ORDER BY views DESC, id DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_animes_count(self) -> int:
        """Jami animelar sonini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM animes")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def delete_anime(self, anime_id: int) -> bool:
        """Animeni o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM episodes WHERE anime_id = ?", (anime_id,))
            cursor = await db.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
            await db.commit()
            return cursor.rowcount > 0

    # ================= Qismlar bilan ishlash =================

    async def add_episode(self, anime_id: int, episode_num: int, file_id: str,
                          file_type: str = "video", caption: Optional[str] = None):
        """Anime qismini qo'shish yoki yangilash"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO episodes (anime_id, episode_num, file_id, file_type, caption)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(anime_id, episode_num) DO UPDATE SET
                    file_id = excluded.file_id,
                    file_type = excluded.file_type,
                    caption = excluded.caption
            """, (anime_id, episode_num, file_id, file_type, caption))
            await db.commit()

    async def get_episode(self, anime_id: int, episode_num: int) -> Optional[Dict[str, Any]]:
        """Aniq qismni olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM episodes WHERE anime_id = ? AND episode_num = ?",
                (anime_id, episode_num)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def get_anime_episodes(self, anime_id: int) -> List[Dict[str, Any]]:
        """Animening yuklangan barcha qismlarini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM episodes WHERE anime_id = ? ORDER BY episode_num ASC",
                (anime_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_episodes_count(self) -> int:
        """Yuklangan qismlar umumiy sonini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM episodes")
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ================= Majburiy obuna kanallari =================

    async def add_sponsor_channel(self, channel_id: str, title: str, invite_link: str) -> bool:
        """Sponsor kanal qo'shish"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
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
            except Exception:
                return False

    async def get_active_sponsor_channels(self) -> List[Dict[str, Any]]:
        """Faol sponsor kanallar ro'yxatini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sponsor_channels WHERE is_active = 1")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_sponsor_channels(self) -> List[Dict[str, Any]]:
        """Barcha sponsor kanallar ro'yxatini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sponsor_channels")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_sponsor_channel(self, channel_id: str) -> bool:
        """Sponsor kanalni o'chirish"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM sponsor_channels WHERE channel_id = ?",
                (channel_id,)
            )
            await db.commit()
            return cursor.rowcount > 0


db = Database()
