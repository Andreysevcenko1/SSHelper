"""Tests for broadcast config parsing and topic-routing helpers."""
import os
import pytest

from app.config import Config, load_config, _parse_optional_int
from app.services.ss_parser import Listing
from app.services.watcher import _normalize, _detect_topic, _is_riga


# ──────────────────────────────────────────────────────────────────────────────
# _parse_optional_int
# ──────────────────────────────────────────────────────────────────────────────

def test_parse_optional_int_empty():
    assert _parse_optional_int("", "X") is None


def test_parse_optional_int_whitespace():
    assert _parse_optional_int("  ", "X") is None


def test_parse_optional_int_valid():
    assert _parse_optional_int("42", "X") == 42
    assert _parse_optional_int(" -100 ", "X") == -100


def test_parse_optional_int_invalid():
    with pytest.raises(ValueError, match="X"):
        _parse_optional_int("abc", "X")


# ──────────────────────────────────────────────────────────────────────────────
# load_config — broadcast disabled by default
# ──────────────────────────────────────────────────────────────────────────────

def test_load_config_broadcast_disabled_by_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake:token")
    monkeypatch.delenv("BROADCAST_ENABLED", raising=False)
    cfg = load_config()
    assert cfg.broadcast_enabled is False
    assert cfg.broadcast_chat_id is None


def test_load_config_broadcast_false_explicit(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake:token")
    monkeypatch.setenv("BROADCAST_ENABLED", "false")
    cfg = load_config()
    assert cfg.broadcast_enabled is False


def test_load_config_broadcast_enabled_requires_all_vars(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake:token")
    monkeypatch.setenv("BROADCAST_ENABLED", "true")
    monkeypatch.setenv("BROADCAST_CHAT_ID", "-1001234567890")
    # Missing THREAD_* vars → should raise
    for var in ("THREAD_IRE_RIGA", "THREAD_SELL_RIGA", "THREAD_AUTO_RIGA", "THREAD_OTHER_CITIES"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValueError, match="BROADCAST_ENABLED=true"):
        load_config()


def test_load_config_broadcast_enabled_all_vars(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake:token")
    monkeypatch.setenv("BROADCAST_ENABLED", "true")
    monkeypatch.setenv("BROADCAST_CHAT_ID", "-1001234567890")
    monkeypatch.setenv("THREAD_IRE_RIGA", "10")
    monkeypatch.setenv("THREAD_SELL_RIGA", "20")
    monkeypatch.setenv("THREAD_AUTO_RIGA", "30")
    monkeypatch.setenv("THREAD_OTHER_CITIES", "40")
    monkeypatch.setenv("THREAD_WORK_RIGA", "50")
    monkeypatch.setenv("THREAD_FLEA_MARKET", "60")
    cfg = load_config()
    assert cfg.broadcast_enabled is True
    assert cfg.broadcast_chat_id == -1001234567890
    assert cfg.thread_ire_riga == 10
    assert cfg.thread_sell_riga == 20
    assert cfg.thread_auto_riga == 30
    assert cfg.thread_other_cities == 40
    assert cfg.thread_work_riga == 50
    assert cfg.thread_flea_market == 60


# ──────────────────────────────────────────────────────────────────────────────
# _normalize
# ──────────────────────────────────────────────────────────────────────────────

def test_normalize_removes_diacritics():
    assert _normalize("Rīga") == "riga"
    assert _normalize("Dzīvokļu īre") == "dzivoklu ire"
    assert _normalize("Pārdošana") == "pardosana"


def test_normalize_lowercases():
    assert _normalize("AUTO") == "auto"


# ──────────────────────────────────────────────────────────────────────────────
# _is_riga
# ──────────────────────────────────────────────────────────────────────────────

def test_is_riga_city():
    assert _is_riga("Rīga", "") is True
    assert _is_riga("riga", "") is True
    assert _is_riga("Rīga", "https://ss.lv/lv/real-estate/flats/other/") is True


def test_is_riga_url():
    assert _is_riga(None, "https://ss.lv/lv/real-estate/flats/riga/") is True


def test_is_riga_other_city():
    assert _is_riga("Daugavpils", "https://ss.lv/lv/real-estate/flats/daugavpils/") is False


def test_is_riga_none():
    assert _is_riga(None, "https://ss.lv/lv/transport/cars/") is False


# ──────────────────────────────────────────────────────────────────────────────
# _detect_topic routing
# ──────────────────────────────────────────────────────────────────────────────

def _make_config(ire=10, sell=20, auto=30, other=40, work=50, flea=60) -> Config:
    return Config(
        telegram_bot_token="fake",
        broadcast_enabled=True,
        broadcast_chat_id=-1001234567890,
        thread_ire_riga=ire,
        thread_sell_riga=sell,
        thread_auto_riga=auto,
        thread_work_riga=work,
        thread_flea_market=flea,
        thread_other_cities=other,
    )


def _listing(title: str = "Test", city: str | None = None) -> Listing:
    return Listing(external_id="123", title=title, url="https://ss.lv/msg/lv/foo/123/", city=city)


def test_route_riga_rent():
    cfg = _make_config()
    listing = _listing(city="Rīga")
    url = "https://ss.lv/lv/real-estate/flats/riga/hand_over/"
    assert _detect_topic(url, listing, cfg) == 10


def test_route_riga_sale():
    cfg = _make_config()
    listing = _listing(city="Rīga")
    url = "https://ss.lv/lv/real-estate/flats/riga/sell/"
    # "sell" is in _SALE_KEYWORDS
    assert _detect_topic(url, listing, cfg) == 20


def test_route_riga_auto():
    cfg = _make_config()
    listing = _listing(city="Rīga")
    url = "https://ss.lv/lv/transport/cars/riga/"
    assert _detect_topic(url, listing, cfg) == 30


def test_route_other_city_rent():
    cfg = _make_config()
    listing = _listing(city="Jūrmala")
    url = "https://ss.lv/lv/real-estate/flats/jurmala/hand_over/"
    assert _detect_topic(url, listing, cfg) == 40


def test_route_other_fallback():
    cfg = _make_config()
    listing = _listing(city="Liepāja")
    url = "https://ss.lv/lv/animals/dogs/liepaja/"
    assert _detect_topic(url, listing, cfg) == 40


def test_route_riga_url_no_city():
    """Riga detected from URL even when city field is None."""
    cfg = _make_config()
    listing = _listing(city=None)
    url = "https://ss.lv/lv/transport/cars/riga/"
    assert _detect_topic(url, listing, cfg) == 30


def test_route_riga_work():
    cfg = _make_config()
    listing = _listing(city="Rīga")
    url = "https://ss.lv/lv/work/are-required/riga/"
    assert _detect_topic(url, listing, cfg) == 50


def test_route_flea_market():
    cfg = _make_config()
    listing = _listing(city="Jūrmala")
    url = "https://ss.lv/lv/market/"
    assert _detect_topic(url, listing, cfg) == 60
