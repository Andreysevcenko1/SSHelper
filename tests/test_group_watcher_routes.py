from app.config import Config
from app.services.group_watcher import _thread_id_for_route_key


def _cfg() -> Config:
    return Config(
        telegram_bot_token="x",
        broadcast_enabled=True,
        broadcast_chat_id=-1001,
        thread_ire_riga=10,
        thread_sell_riga=20,
        thread_auto_riga=30,
        thread_work_riga=50,
        thread_flea_market=60,
        thread_other_cities=40,
    )


def test_group_route_work_riga_maps_to_thread():
    assert _thread_id_for_route_key("work_riga", _cfg()) == 50


def test_group_route_flea_market_maps_to_thread():
    assert _thread_id_for_route_key("flea_market", _cfg()) == 60
