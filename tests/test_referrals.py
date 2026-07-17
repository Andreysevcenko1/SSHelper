"""Tests for the invite-a-friend referral system."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Search, UserSettings
from app.db.repo import ReferralRepository, SubscriptionRepository
from app.i18n import get_text


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def test_credit_new_user(session):
    repo = ReferralRepository(session)
    assert repo.credit(referrer_id=1, invitee_id=2) is True
    assert repo.bonus_slots(1) == 1


def test_no_self_referral(session):
    repo = ReferralRepository(session)
    assert repo.credit(referrer_id=1, invitee_id=1) is False
    assert repo.bonus_slots(1) == 0


def test_no_double_credit_same_invitee(session):
    repo = ReferralRepository(session)
    assert repo.credit(1, 2) is True
    assert repo.credit(1, 2) is False
    assert repo.credit(3, 2) is False  # even by another referrer
    assert repo.bonus_slots(1) == 1
    assert repo.bonus_slots(3) == 0


def test_known_user_not_credited(session):
    session.add(UserSettings(user_id=5, selected_language="ru"))
    session.commit()
    repo = ReferralRepository(session)
    assert repo.credit(1, 5) is False

    session.add(Search(user_id=6, url="https://www.ss.lv/lv/real-estate/flats/riga/"))
    session.commit()
    assert repo.credit(1, 6) is False


def test_bonus_capped(session):
    repo = ReferralRepository(session)
    for i in range(2, 2 + ReferralRepository.MAX_BONUS + 5):
        repo.credit(1, i)
    assert repo.bonus_slots(1) == ReferralRepository.MAX_BONUS


def test_limit_includes_referral_bonus(session):
    ref = ReferralRepository(session)
    sub = SubscriptionRepository(session)
    assert sub.active_search_limit(1) == 1
    ref.credit(1, 2)
    ref.credit(1, 3)
    assert sub.active_search_limit(1) == 3
    sub.set_plan(1, "plus4", 4)
    assert sub.active_search_limit(1) == 7


def test_ref_i18n_keys():
    for lang in ("lv", "ru", "en"):
        assert get_text("btn_invite_friend", lang)
        txt = get_text("ref_screen", lang, link="L", count=1, max=10)
        assert "L" in txt
        assert get_text("ref_credited", lang)
