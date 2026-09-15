from dataclasses import dataclass, field
import json
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass(slots=True)
class FacebookPageTarget:
    page_id: str
    access_token: str


@dataclass(slots=True)
class Config:
    telegram_bot_token: str
    database_url: str = "sqlite:///./sshelper.db"
    poll_interval_seconds: int = 120
    group_poll_interval_seconds: int = 120
    # Broadcast / forum-topic delivery
    broadcast_enabled: bool = False
    broadcast_chat_id: Optional[int] = None
    thread_ire_riga: Optional[int] = None
    thread_sell_riga: Optional[int] = None
    thread_auto_riga: Optional[int] = None
    thread_other_cities: Optional[int] = None
    thread_work_riga: Optional[int] = None
    thread_flea_market: Optional[int] = None
    # Admin user IDs allowed to manage group searches (comma-separated in env)
    admin_user_ids: list[int] = field(default_factory=list)
    # Facebook Page auto-posting (Graph API) — optional
    facebook_enabled: bool = False
    facebook_page_id: Optional[str] = None
    facebook_page_access_token: Optional[str] = None
    facebook_route_targets: dict[str, FacebookPageTarget] = field(default_factory=dict)


def _parse_optional_int(raw: str, name: str) -> Optional[int]:
    """Return int if *raw* is non-empty, else None. Raises ValueError on bad input."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc


def _parse_facebook_route_targets(raw: str) -> dict[str, FacebookPageTarget]:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("FACEBOOK_ROUTE_TARGETS_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("FACEBOOK_ROUTE_TARGETS_JSON must be a JSON object")

    targets: dict[str, FacebookPageTarget] = {}
    for route_key, value in parsed.items():
        if not isinstance(route_key, str) or not isinstance(value, dict):
            raise ValueError(
                "FACEBOOK_ROUTE_TARGETS_JSON must map route keys to objects"
            )
        page_id = str(value.get("page_id", "")).strip()
        access_token = str(value.get("access_token", "")).strip()
        if not page_id or not access_token:
            raise ValueError(
                f"FACEBOOK_ROUTE_TARGETS_JSON target {route_key!r} requires page_id and access_token"
            )
        targets[route_key] = FacebookPageTarget(
            page_id=page_id,
            access_token=access_token,
        )
    return targets


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

    group_poll_interval_raw = os.getenv("GROUP_POLL_INTERVAL_SECONDS", poll_interval_raw).strip()
    try:
        group_poll_interval_seconds = max(int(group_poll_interval_raw), 30)
    except ValueError as exc:
        raise ValueError("GROUP_POLL_INTERVAL_SECONDS must be an integer") from exc

    # Admin user IDs (comma-separated)
    admin_ids_raw = os.getenv("ADMIN_USER_IDS", "").strip()
    admin_user_ids: list[int] = []
    if admin_ids_raw:
        for part in admin_ids_raw.split(","):
            part = part.strip()
            if part:
                try:
                    admin_user_ids.append(int(part))
                except ValueError as exc:
                    raise ValueError(f"ADMIN_USER_IDS contains non-integer value: {part!r}") from exc

    # Broadcast config
    broadcast_enabled_raw = os.getenv("BROADCAST_ENABLED", "false").strip().lower()
    broadcast_enabled = broadcast_enabled_raw in {"1", "true", "yes"}

    broadcast_chat_id = _parse_optional_int(os.getenv("BROADCAST_CHAT_ID", ""), "BROADCAST_CHAT_ID")
    thread_ire_riga = _parse_optional_int(os.getenv("THREAD_IRE_RIGA", ""), "THREAD_IRE_RIGA")
    thread_sell_riga = _parse_optional_int(os.getenv("THREAD_SELL_RIGA", ""), "THREAD_SELL_RIGA")
    thread_auto_riga = _parse_optional_int(os.getenv("THREAD_AUTO_RIGA", ""), "THREAD_AUTO_RIGA")
    thread_other_cities = _parse_optional_int(os.getenv("THREAD_OTHER_CITIES", ""), "THREAD_OTHER_CITIES")
    thread_work_riga = _parse_optional_int(os.getenv("THREAD_WORK_RIGA", ""), "THREAD_WORK_RIGA")
    thread_flea_market = _parse_optional_int(os.getenv("THREAD_FLEA_MARKET", ""), "THREAD_FLEA_MARKET")

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

    # Facebook Page auto-posting config
    facebook_enabled_raw = os.getenv("FACEBOOK_ENABLED", "false").strip().lower()
    facebook_enabled = facebook_enabled_raw in {"1", "true", "yes"}
    facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip() or None
    facebook_page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip() or None
    facebook_route_targets = _parse_facebook_route_targets(
        os.getenv("FACEBOOK_ROUTE_TARGETS_JSON", "")
    )

    if facebook_enabled:
        missing_fb = []
        has_default_target = bool(facebook_page_id and facebook_page_access_token)
        if not has_default_target and not facebook_route_targets:
            missing_fb.append("FACEBOOK_PAGE_ID")
            missing_fb.append("FACEBOOK_PAGE_ACCESS_TOKEN")
        elif bool(facebook_page_id) != bool(facebook_page_access_token):
            if not facebook_page_id:
                missing_fb.append("FACEBOOK_PAGE_ID")
            if not facebook_page_access_token:
                missing_fb.append("FACEBOOK_PAGE_ACCESS_TOKEN")
        if missing_fb:
            raise ValueError(
                "FACEBOOK_ENABLED=true requires either FACEBOOK_PAGE_ID + "
                "FACEBOOK_PAGE_ACCESS_TOKEN or FACEBOOK_ROUTE_TARGETS_JSON; "
                f"missing: {', '.join(missing_fb)}"
            )

    return Config(
        telegram_bot_token=token,
        database_url=database_url,
        poll_interval_seconds=poll_interval_seconds,
        group_poll_interval_seconds=group_poll_interval_seconds,
        broadcast_enabled=broadcast_enabled,
        broadcast_chat_id=broadcast_chat_id,
        thread_ire_riga=thread_ire_riga,
        thread_sell_riga=thread_sell_riga,
        thread_auto_riga=thread_auto_riga,
        thread_other_cities=thread_other_cities,
        thread_work_riga=thread_work_riga,
        thread_flea_market=thread_flea_market,
        admin_user_ids=admin_user_ids,
        facebook_enabled=facebook_enabled,
        facebook_page_id=facebook_page_id,
        facebook_page_access_token=facebook_page_access_token,
        facebook_route_targets=facebook_route_targets,
    )
