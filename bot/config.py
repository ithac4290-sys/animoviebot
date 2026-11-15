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
    database_url: str
    trace_moe_api_key: str
    manga_webapp_url: str
    shorts_webapp_url: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "8985548481:AAGrObZ8YwZgV9mP0EOCPg2zn-EIELZgruY").strip()
    bot_username = os.getenv("BOT_USERNAME", "AniMovieuz_bot").strip().lstrip("@")
    channel_id = os.getenv("DEFAULT_CHANNEL_ID", "@Ani_Movei_UZ").strip()
    db_name = os.getenv("DB_NAME", "anime_bot.db").strip()
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_2jclL6yKbCer@ep-round-truth-bbk4ma0f-pooler.c-15.us-east-1.aws.neon.tech/neondb?sslmode=require"
    ).strip()

    trace_moe_api_key = os.getenv("TRACE_MOE_API_KEY", "").strip()
    manga_webapp_url = os.getenv("MANGA_WEBAPP_URL", "https://ithac4290-sys.github.io/animoviebot/manga/?v=3").strip()
    shorts_webapp_url = os.getenv("SHORTS_WEBAPP_URL", "https://ithac4290-sys.github.io/animoviebot/shorts/?v=3").strip()

    admins_raw = os.getenv("ADMINS", "7285523919,8166740229")
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
        database_url=database_url,
        trace_moe_api_key=trace_moe_api_key,
        manga_webapp_url=manga_webapp_url,
        shorts_webapp_url=shorts_webapp_url,
    )


config = load_config()
