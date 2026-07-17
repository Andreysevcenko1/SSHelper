"""Tests for the 30-day free trial and post-trial limits."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Referral, Trial
from app.db.repo import ReferralRepository, SubscriptionRepository, TrialRepository
from app.i18n import get_text


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def _expire_trial(session, user_id):
    trial = session.get(Trial, user_id)
    trial.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()


def test_trial_starts_lazily(session):
    repo = TrialRepository(session)
    assert repo.is_active(1) is True
    assert 29 <= repo.days_left(1) <= 30


def test_trial_gives_one_slot(session):
    sub = SubscriptionRepository(session)
    assert sub.active_search_limit(1) == 1


def test_expired_trial_gives_zero(session):
    sub = SubscriptionRepository(session)
    assert sub.active_search_limit(1) == 1
    _expire_trial(session, 1)
    assert sub.active_search_limit(1) == 0


def test_paid_plan_after_trial(session):
    sub = SubscriptionRepository(session)
    sub.active_search_limit(1)
    _expire_trial(session, 1)
    sub.set_plan(1, "plus4", 5)
    assert sub.active_search_limit(1) == 5


def test_referral_bonus_after_trial(session):
    sub = SubscriptionRepository(session)
    ref = ReferralRepository(session)
    sub.active_search_limit(1)
    _expire_trial(session, 1)
    ref.credit(1, 2)
    assert sub.active_search_limit(1) == 1


def test_referral_bonus_expires_after_30_days(session):
    sub = SubscriptionRepository(session)
    ref = ReferralRepository(session)
    ref.credit(1, 2)
    row = session.get(Referral, 2)
    row.created_at = datetime.utcnow() - timedelta(days=31)
    session.commit()
    assert ref.bonus_slots(1) == 0


def test_trial_i18n_keys():
    for lang in ("lv", "ru", "en"):
        assert get_text("sub_status_trial", lang, days=5)
        assert get_text("sub_status_expired", lang)
        assert get_text("trial_expired_paused", lang, count=2)
