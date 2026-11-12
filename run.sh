#!/usr/bin/env bash

# Loyiha papkasiga o'tish
cd "$(dirname "$0")"

echo "=========================================="
echo "🎬 Anime Telegram Bot Ishga Tushirilmoqda..."
echo "=========================================="

# Agar .venv mavjud bo'lsa, undan foydalanish
if [ -d ".venv" ]; then
    .venv/bin/python main.py
elif [ -d "venv" ]; then
    venv/bin/python main.py
else
    python3 main.py
fi
