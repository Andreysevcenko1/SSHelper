from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(slots=True)
class Config:
    telegram_bot_token: str
    database_url: str = "sqlite:///./sshelper.db"
    poll_interval_seconds: int = 120



def load_config() -> Config:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    database_url = os.getenv("DATABASE_URL", "sqlite:///./sshelper.db").strip()
    poll_interval_raw = os.getenv("POLL_INTERVAL_SECONDS", "120").strip()

    try:
        poll_interval_seconds = max(int(poll_interval_raw), 30)
    except ValueError as exc:
        raise ValueError("POLL_INTERVAL_SECONDS must be an integer") from exc

    return Config(
        telegram_bot_token=token,
        database_url=database_url,
        poll_interval_seconds=poll_interval_seconds,
    )
