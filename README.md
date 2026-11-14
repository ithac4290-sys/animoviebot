# 🎬 Anime Telegram Bot (aiogram 3.x + Neon PostgreSQL JSONB)

Mukammal arxitekturaga ega, tezkor va zamonaviy Anime Telegram Boti. Bot anime ko'rish, qismlarni tomosha qilish, majburiy sponsor obunasini tekshirish, admin boshqaruv paneli, Neon Serverless PostgreSQL bazasida barcha video va qismlarni JSONB formatda saqlash va Railway bulutli serverida uzluksiz ishlashga to'liq moslashtirilgan.

---

## 🌟 Asosiy Imkoniyatlar

1. **Asosiy Bosh Menyu (`/start`):**
   - Chiroyli formatlangan xush kelibsiz matni (HTML parse_mode).
   - `[ 🔎 Anime izlash ]` (Telegram Inline qidiruv rejimi).
   - `[ 📄 Manga kurish ]` va `[ 🔴 Shorts kurish ]`.
   - `[ 🗄 Kabinet ]` va `[ 💎 VIP Obuna ]`.
   - To'g'ridan-to'g'ri Anime kodi (masalan `961`) yoki nomi yozilganda darhol topib berish.

2. **Kanalga Avtomatik Post Joylash (Admin Panel):**
   - Admin `/admin` menyusi orqali yangi anime qo'shadi (Nomi, Posteri, Holati, Qismlar soni, Janrlari, Kanal username).
   - Standart `@Ani_Movei_UZ` kanalini bitta tugma bilan tanlash imkoniyati.
   - Bot noyob **Anime ID** yaratadi va kanalda avtomatik post joylaydi:
     - `▶️ Tomosha qilish` tugmasi
     - `📚 Barcha qismlar` tugmasi

3. **Neon Serverless PostgreSQL & JSON Formatda Saqlash:**
   - Barcha anime ma'lumotlari, video fayllari (`file_id`), qismlar va ko'rishlar soni PostgreSQL `JSONB` ustunlarida strukturaviy JSON formatda saqlanadi.
   - Qismlar yuklanganda `jsonb_set` orqali ma'lumotlar real vaqtda yangilanadi.

4. **Anime Menyusi va Qismlar Gridi:**
   - 4 tadan ustun (grid) qilib joylashtirilgan qism tugmalari (`[ ▶️ 1 - qism ]` `[ ▶️ 2 - qism ]` ...).
   - Eng pastda alohida `❌ Yopish` tugmasi.
   - Qism tanlanganda videoni tezkor yuborish.

5. **Qulay Admin Boshqaruv Paneli (`/admin`):**
   - ➕ **Yangi anime qo'shish**: Rasm yoki fotosurat fayli orqali, standart kanal tanlash bilan.
   - 🎬 **Qism yuklash**: Oxirgi animelar ro'yxatidan tanlash va keyingi qismlarni ketma-ket uzluksiz yuklash.
   - 📋 **Animelar ro'yxati**: Barcha animelarni sahifalab ko'rish, boshqarish va o'chirish.
   - 📢 **Sponsor kanallar**: Majburiy a'zolik kanallarini qo'shish va boshqarish.
   - 💎 **VIP boshqaruvi**: Foydalanuvchilarga VIP berish, cheklarni tasdiqlash/rad etish.
   - 📊 **Kengaytirilgan statistika**: Foydalanuvchilar, VIP lar, animelar, yuklangan videolar, ko'rishlar soni va Neon DB holati.
   - ✉️ **Broadcast**: Barcha foydalanuvchilarga xabar tarqatish.

---

## 🚀 Ishga Tushirish va O'rnatish

### 1. Repozitoriyani klonlash:
```bash
git clone https://github.com/ithac4290-sys/animoviebot.git
cd animoviebot
```

### 2. Virtual muhit va kutubxonalarni o'rnatish:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Sozlamalarni kiritish (.env):
```env
BOT_TOKEN=Sizning_Bot_Tokeningiz
ADMINS=7285523919
DEFAULT_CHANNEL_ID=@Ani_Movei_UZ
DATABASE_URL=postgresql://neondb_owner:parol@ep-rough-rain-befo0pja-pooler.c-9.us-east-2.aws.neon.tech/neondb?sslmode=require
```

### 4. Botni ishga tushirish:
```bash
python3 main.py
```

---

## 📁 Loyiha Strukturasi

```text
├── bot/
│   ├── config.py             # Sozlamalar
│   ├── database.py           # Neon PostgreSQL (JSONB) va aiosqlite
│   ├── filters.py            # Admin filter
│   ├── keyboards.py          # Barcha inline va reply tugmalar
│   ├── middlewares.py        # Foydalanuvchini ro'yxatga olish
│   ├── states.py             # FSM holatlari
│   ├── utils.py              # Obunani tekshirish funksiyalari
│   └── handlers/
│       ├── admin.py          # Admin boshqaruv paneli
│       ├── users.py          # Foydalanuvchi buyruqlari va bosh menyu
│       └── inline_search.py  # Inline rejimida qidiruv
├── .env.example              # Namuna sozlamalar
├── .gitignore                # Gitdan chetlatilgan fayllar
├── requirements.txt          # Kerakli paketlar
├── main.py                   # Botni ishga tushiruvchi fayl
└── README.md                 # Qo'llanma
```
