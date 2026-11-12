# 🎬 Anime Telegram Bot (aiogram 3.x + SQLite)

Mukammal arxitekturaga ega, tezkor va zamonaviy Anime Telegram Boti. Bot anime ko'rish, qismlarni tomosha qilish, majburiy obunani tekshirish, admin panel va kanalga avtomatik chiroyli post joylash imkoniyatlariga ega.

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
   - Bot noyob **Anime ID** yaratadi va kanalda avtomatik post joylaydi:
     - `▶️ Tomosha qilish` tugmasi
     - `📚 Barcha qismlar` tugmasi

3. **Anime Menyusi va Qismlar Gridi:**
   - 4 tadan ustun (grid) qilib joylashtirilgan qism tugmalari (`[ 1 - qism ]` `[ 2 - qism ]` ...).
   - Eng pastda alohida `❌ Yopish` tugmasi.
   - Qism tanlanganda videoni tezkor yuborish.

4. **Qo'shimcha Imkoniyatlar:**
   - 🎬 **Qism yuklash:** Admin panel orqali har bir qism uchun video yuklash.
   - 📢 **Majburiy obuna (Sponsor kanallar):** Obunani tekshirish tizimi.
   - 💎 **VIP Tizimi:** VIP foydalanuvchilar kanallarga obuna bo'lmasdan tomosha qiladi.
   - 📊 **Statistika:** Foydalanuvchilar, animelar va qismlar soni.
   - ✉️ **Broadcast:** Barcha foydalanuvchilarga xabar tarqatish.

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Repozitoriyani klonlash:
```bash
git clone https://github.com/ithac4290-sys/animoviebot.git
cd animoviebot
```

### 2. Virtual muhit yaratish va faollashtirish:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux / macOS
# yoki Windows uchun:
# venv\Scripts\activate
```

### 3. Kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

### 4. Sozlamalarni kiritish (.env):
`.env.example` faylidan nusxa olib `.env` yarating:
```bash
cp .env.example .env
```
Va ichiga bot tokeningiz hamda admin ID raqamingizni yozing:
```env
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
BOT_USERNAME=your_bot_username
ADMINS=123456789
DEFAULT_CHANNEL_ID=@your_channel_username
DB_NAME=anime_bot.db
```

### 5. Botni ishga tushirish:
```bash
python3 main.py
```

---

## 📁 Loyiha Strukturasi

```text
├── bot/
│   ├── config.py             # Sozlamalar
│   ├── database.py           # aiosqlite ma'lumotlar bazasi
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
