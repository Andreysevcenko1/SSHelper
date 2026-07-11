"""Tests for subscription plans, limits, and brand-from-URL logic."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Subscription
from app.db.repo import SearchRepository, SubscriptionRepository
from app.i18n import get_text
from app.services.plans import PLAN_DURATION_DAYS, PLANS
from app.bot.handlers.add_search import (
    _extract_cars_path_slugs,
    _resolve_cars_brand_from_url,
    _strip_query_keys,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


# ------------------------- plans -------------------------


def test_plans_definition():
    assert set(PLANS) == {"plus1", "plus4", "plus9"}
    assert PLANS["plus1"].extra_searches == 1
    assert PLANS["plus4"].extra_searches == 4
    assert PLANS["plus9"].extra_searches == 9
    assert PLAN_DURATION_DAYS == 30


def test_plan_totals():
    for plan in PLANS.values():
        assert plan.total_searches == plan.extra_searches + 1


# ------------------------- repository -------------------------


def test_free_limit_default(session):
    repo = SubscriptionRepository(session)
    assert repo.active_search_limit(1) == 1
    assert repo.get_active(1) is None


def test_set_plan_increases_limit(session):
    repo = SubscriptionRepository(session)
    repo.set_plan(1, "plus4", 4)
    assert repo.active_search_limit(1) == 5
    sub = repo.get_active(1)
    assert sub is not None and sub.plan == "plus4"


def test_new_plan_replaces_old(session):
    repo = SubscriptionRepository(session)
    repo.set_plan(1, "plus9", 9)
    repo.set_plan(1, "plus1", 1)
    sub = repo.get_active(1)
    assert sub.plan == "plus1"
    assert repo.active_search_limit(1) == 2


def test_expired_plan_reverts_to_free(session):
    repo = SubscriptionRepository(session)
    repo.set_plan(1, "plus4", 4)
    sub = session.get(Subscription, 1)
    sub.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    assert repo.get_active(1) is None
    assert repo.active_search_limit(1) == 1


def test_count_active_for_user(session):
    repo = SearchRepository(session)
    s1 = repo.add_search(user_id=1, url="https://www.ss.lv/lv/transport/cars/", title="c")
    repo.add_search(user_id=1, url="https://www.ss.lv/lv/real-estate/flats/", title="f")
    repo.add_search(user_id=2, url="https://www.ss.lv/lv/transport/cars/audi/", title="c")
    assert repo.count_active_for_user(1) == 2
    repo.pause_search(s1)
    assert repo.count_active_for_user(1) == 1


# ------------------------- brand-from-URL -------------------------


def test_extract_cars_path_slugs():
    assert _extract_cars_path_slugs("https://www.ss.lv/lv/transport/cars/saab/") == ("saab", None)
    assert _extract_cars_path_slugs("https://www.ss.lv/lv/transport/cars/bmw/3-series/") == ("bmw", "3-series")
    assert _extract_cars_path_slugs("https://www.ss.lv/lv/transport/cars/") == (None, None)
    assert _extract_cars_path_slugs("https://www.ss.lv/lv/real-estate/flats/riga/") == (None, None)


def test_resolve_brand_autofill_from_path():
    status, url, applied, _ = _resolve_cars_brand_from_url(
        "https://www.ss.lv/lv/transport/cars/saab/"
    )
    assert status == "ok"
    assert applied == "saab"
    assert "opt%5B14%5D=saab" in url


def test_resolve_brand_with_model():
    status, url, applied, _ = _resolve_cars_brand_from_url(
        "https://www.ss.lv/lv/transport/cars/bmw/3-series/"
    )
    assert status == "ok"
    assert "opt%5B14%5D=bmw" in url and "opt%5B15%5D=3-series" in url


def test_resolve_brand_conflict_detected():
    status, _url, path_brand, q_brand = _resolve_cars_brand_from_url(
        "https://www.ss.lv/lv/transport/cars/saab/?opt%5B14%5D=audi"
    )
    assert status == "conflict"
    assert path_brand == "saab"
    assert q_brand == "audi"


def test_resolve_brand_same_no_conflict():
    status, _url, applied, _ = _resolve_cars_brand_from_url(
        "https://www.ss.lv/lv/transport/cars/audi/?opt%5B14%5D=audi"
    )
    assert status == "ok"
    assert applied is None


def test_resolve_no_path_brand_untouched():
    src = "https://www.ss.lv/lv/transport/cars/?opt%5B14%5D=audi"
    status, url, applied, _ = _resolve_cars_brand_from_url(src)
    assert status == "ok"
    assert url == src
    assert applied is None


def test_strip_query_keys():
    url = "https://x.lv/a/?opt%5B14%5D=audi&opt%5B8%5D%5Bmax%5D=5000"
    out = _strip_query_keys(url, {"opt[14]"})
    assert "opt%5B14%5D" not in out
    assert "5000" in out


# ------------------------- i18n -------------------------


@pytest.mark.parametrize("lang", ["ru", "lv", "en"])
def test_i18n_subscription_keys(lang):
    assert get_text("btn_subscription", lang)
    assert get_text("sub_screen_title", lang)
    assert get_text("err_search_limit", lang, limit=1)
    assert get_text("btn_buy_more_searches", lang)
    assert get_text("brand_from_url_applied", lang, brand="Saab")
    assert get_text("brand_conflict_question", lang, url_brand="Saab", filter_brand="Audi")
    assert get_text("btn_replace_brand", lang)
    assert get_text("btn_keep_brand", lang)
    assert get_text("sub_paid_ok", lang, total=2, days=30)


def test_plan_i18n_texts():
    for lang in ("ru", "lv", "en"):
        for plan in PLANS.values():
            assert get_text(plan.label_i18n_key, lang, eur=plan.price_eur, stars=plan.price_stars)


def test_plan_star_prices():
    assert PLANS["plus1"].price_stars == 100
    assert PLANS["plus4"].price_stars == 250
    assert PLANS["plus9"].price_stars == 500


def test_find_duplicate_same_url_different_filters(session):
    repo = SearchRepository(session)
    repo.add_search(
        user_id=1, url="https://www.ss.lv/lv/transport/cars/audi/", title="c",
        base_url="https://www.ss.lv/lv/transport/cars/audi/", filters_json='{"opt[8][max]": "5000"}',
    )
    assert repo.find_duplicate(1, "https://www.ss.lv/lv/transport/cars/audi/", '{"opt[8][max]": "9000"}') is None
    assert repo.find_duplicate(1, "https://www.ss.lv/lv/transport/cars/audi/", '{"opt[8][max]": "5000"}') is not None
    assert repo.find_duplicate(1, "https://www.ss.lv/lv/transport/cars/audi/", None) is None


def test_display_numbers_sequential_after_delete(session):
    repo = SearchRepository(session)
    s1 = repo.add_search(user_id=1, url="https://www.ss.lv/lv/a/", title="a")
    s2 = repo.add_search(user_id=1, url="https://www.ss.lv/lv/b/", title="b")
    repo.delete_search(s1)
    s3 = repo.add_search(user_id=1, url="https://www.ss.lv/lv/c/", title="c")
    nums = repo.display_numbers(1)
    assert nums[s2.id] == 1
    assert nums[s3.id] == 2
    assert repo.display_no(s3) == 2
