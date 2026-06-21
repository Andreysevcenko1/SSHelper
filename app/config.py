from dataclasses import dataclass, field
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass(slots=True)
class Config:
    telegram_bot_token: str
    database_url: str = "sqlite:///./sshelper.db"
    poll_interval_seconds: int = 120
    # Broadcast / forum-topic delivery
    broadcast_enabled: bool = False
    broadcast_chat_id: Optional[int] = None
    thread_ire_riga: Optional[int] = None
    thread_sell_riga: Optional[int] = None
    thread_auto_riga: Optional[int] = None
    thread_other_cities: Optional[int] = None


def _parse_optional_int(raw: str, name: str) -> Optional[int]:
    """Return int if *raw* is non-empty, else None. Raises ValueError on bad input."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc


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

    # Broadcast config
    broadcast_enabled_raw = os.getenv("BROADCAST_ENABLED", "false").strip().lower()
    broadcast_enabled = broadcast_enabled_raw in {"1", "true", "yes"}

    broadcast_chat_id = _parse_optional_int(os.getenv("BROADCAST_CHAT_ID", ""), "BROADCAST_CHAT_ID")
    thread_ire_riga = _parse_optional_int(os.getenv("THREAD_IRE_RIGA", ""), "THREAD_IRE_RIGA")
    thread_sell_riga = _parse_optional_int(os.getenv("THREAD_SELL_RIGA", ""), "THREAD_SELL_RIGA")
    thread_auto_riga = _parse_optional_int(os.getenv("THREAD_AUTO_RIGA", ""), "THREAD_AUTO_RIGA")
    thread_other_cities = _parse_optional_int(os.getenv("THREAD_OTHER_CITIES", ""), "THREAD_OTHER_CITIES")

    if broadcast_enabled:
        missing = []
        if broadcast_chat_id is None:
            missing.append("BROADCAST_CHAT_ID")
        if thread_ire_riga is None:
            missing.append("THREAD_IRE_RIGA")
        if thread_sell_riga is None:
            missing.append("THREAD_SELL_RIGA")
        if thread_auto_riga is None:
            missing.append("THREAD_AUTO_RIGA")
        if thread_other_cities is None:
            missing.append("THREAD_OTHER_CITIES")
        if missing:
            raise ValueError(
                f"BROADCAST_ENABLED=true requires these env vars to be set: {', '.join(missing)}"
            )

    return Config(
        telegram_bot_token=token,
        database_url=database_url,
        poll_interval_seconds=poll_interval_seconds,
        broadcast_enabled=broadcast_enabled,
        broadcast_chat_id=broadcast_chat_id,
        thread_ire_riga=thread_ire_riga,
        thread_sell_riga=thread_sell_riga,
        thread_auto_riga=thread_auto_riga,
        thread_other_cities=thread_other_cities,
    )
