import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    bot_username: str
    admins: List[int]
    default_channel_id: str
    db_name: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    bot_username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    channel_id = os.getenv("DEFAULT_CHANNEL_ID", "").strip()
    db_name = os.getenv("DB_NAME", "anime_bot.db").strip()

    admins_raw = os.getenv("ADMINS", "")
    admins: List[int] = []
    for admin_id in admins_raw.split(","):
        admin_id = admin_id.strip()
        if admin_id.isdigit():
            admins.append(int(admin_id))

    return Config(
        bot_token=token,
        bot_username=bot_username,
        admins=admins,
        default_channel_id=channel_id,
        db_name=db_name,
    )


config = load_config()
