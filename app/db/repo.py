import json
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    BroadcastSent,
    GroupSearch,
    Referral,
    Search,
    Subscription,
    Trial,
    UserSettings,
)
from app.services.filters import (
    build_effective_url,
    filters_from_json,
    filters_to_json,
    normalize_filters,
)


class UserSettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_lang(self, user_id: int) -> str | None:
        """Return the stored language code for *user_id*, or None."""
        row = self.session.get(UserSettings, user_id)
        return row.selected_language if row else None

    def set_lang(self, user_id: int, lang: str) -> None:
        """Persist the selected language for *user_id*."""
        row = self.session.get(UserSettings, user_id)
        if row is None:
            row = UserSettings(user_id=user_id, selected_language=lang)
            self.session.add(row)
        else:
            row.selected_language = lang
        self.session.commit()


class SearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_search(
        self,
        user_id: int,
        url: str,
        title: str = "SS.lv search",
        base_url: str | None = None,
        filters_json: str | None = None,
        effective_url: str | None = None,
        category_profile: str | None = None,
    ) -> Search:
        search = Search(
            user_id=user_id,
            url=url,
            title=title,
            base_url=base_url,
            filters_json=filters_json,
            effective_url=effective_url,
            category_profile=category_profile,
        )
        self.session.add(search)
        self.session.commit()
        self.session.refresh(search)
        return search

    def get_active_searches(self) -> list[Search]:
        stmt = select(Search).where(Search.is_active.is_(True))
        return list(self.session.scalars(stmt).all())

    def get_user_searches(self, user_id: int) -> list[Search]:
        stmt = select(Search).where(Search.user_id == user_id).order_by(Search.id)
        return list(self.session.scalars(stmt).all())

    def count_active_for_user(self, user_id: int) -> int:
        stmt = select(Search).where(Search.user_id == user_id, Search.is_active.is_(True))
        return len(list(self.session.scalars(stmt).all()))

    def display_numbers(self, user_id: int) -> dict[int, int]:
        """Map search.id → 1-based position in the user's list (stable, ordered by id)."""
        stmt = select(Search.id).where(Search.user_id == user_id).order_by(Search.id)
        return {sid: n for n, sid in enumerate(self.session.scalars(stmt), start=1)}

    def display_no(self, search: Search) -> int:
        """1-based display number of *search* within its owner's searches."""
        return self.display_numbers(search.user_id).get(search.id, search.id)

    def get_by_id(self, search_id: int) -> Search | None:
        return self.session.get(Search, search_id)

    def find_by_base_url(self, user_id: int, base_url: str) -> Search | None:
        """Return the first search for *user_id* whose base_url matches, or None."""
        stmt = (
            select(Search)
            .where(Search.user_id == user_id, Search.base_url == base_url)
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def find_duplicate(self, user_id: int, base_url: str, filters_json: str | None) -> Search | None:
        """Return a search with the same base_url AND identical filters, or None."""
        stmt = select(Search).where(Search.user_id == user_id, Search.base_url == base_url)
        wanted = filters_json or "{}"
        for search in self.session.scalars(stmt):
            if (search.filters_json or "{}") == wanted:
                return search
        return None

    def pause_search(self, search: Search) -> None:
        search.is_active = False
        self.session.add(search)
        self.session.commit()

    def resume_search(self, search: Search) -> None:
        search.is_active = True
        self.session.add(search)
        self.session.commit()

    def delete_search(self, search: Search) -> None:
        self.session.delete(search)
        self.session.commit()

    def update_last_seen(self, search: Search, external_id: str) -> None:
        search.last_seen_external_id = external_id
        self.session.add(search)
        self.session.commit()

    # ------------------------------------------------------------------ #
    # Filter CRUD                                                          #
    # ------------------------------------------------------------------ #

    def set_filter(self, search: Search, field: str, value: str) -> None:
        """Add or update a single filter key-value pair and rebuild effective_url."""
        filters = filters_from_json(search.filters_json)
        filters[field] = value
        normalized = normalize_filters(filters)
        search.filters_json = filters_to_json(normalized)
        if search.base_url:
            search.effective_url = build_effective_url(search.base_url, normalized)
        self.session.add(search)
        self.session.commit()

    def delete_filter(self, search: Search, field: str) -> bool:
        """Remove a single filter key. Returns True if the key existed."""
        filters = filters_from_json(search.filters_json)
        if field not in filters:
            return False
        del filters[field]
        normalized = normalize_filters(filters)
        search.filters_json = filters_to_json(normalized)
        if search.base_url:
            search.effective_url = build_effective_url(search.base_url, normalized)
        self.session.add(search)
        self.session.commit()
        return True

    def clear_filters(self, search: Search) -> None:
        """Remove all filter overrides and reset effective_url to base_url."""
        search.filters_json = None
        search.effective_url = search.base_url or search.url
        self.session.add(search)
        self.session.commit()

    # ------------------------------------------------------------------ #
    # DB Hygiene                                                           #
    # ------------------------------------------------------------------ #

    def prune_old_inactive_searches(self, older_than_days: int = 90) -> int:
        """Delete paused searches older than *older_than_days* days.

        Returns the number of deleted rows.
        Only removes searches that have been paused since creation
        (last_seen_external_id is None) — i.e. never actually ran.
        These are effectively orphaned records.
        """
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        stmt = select(Search).where(
            Search.is_active.is_(False),
            Search.last_seen_external_id.is_(None),
            Search.created_at < cutoff,
        )
        old_searches = list(self.session.scalars(stmt).all())
        for s in old_searches:
            self.session.delete(s)
        if old_searches:
            self.session.commit()
        return len(old_searches)

    def vacuum(self) -> None:
        """Run VACUUM on the database (SQLite only, no-op for other engines).

        Reclaims space freed by deleted rows.
        """
        try:
            self.session.execute(text("VACUUM"))
        except Exception:
            pass  # Not supported on all engines (e.g. PostgreSQL in transactions)


class GroupSearchRepository:
    """Repository for group-level searches that are broadcast to forum topics."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_group_search(
        self,
        title: str,
        url: str,
        route_key: str = "other",
        base_url: str | None = None,
        filters_json: str | None = None,
        effective_url: str | None = None,
        category_profile: str | None = None,
    ) -> GroupSearch:
        search = GroupSearch(
            title=title,
            url=url,
            route_key=route_key,
            base_url=base_url,
            filters_json=filters_json,
            effective_url=effective_url,
            category_profile=category_profile,
        )
        self.session.add(search)
        self.session.commit()
        self.session.refresh(search)
        return search

    def get_active_group_searches(self) -> list[GroupSearch]:
        stmt = select(GroupSearch).where(GroupSearch.is_active.is_(True))
        return list(self.session.scalars(stmt).all())

    def get_group_searches(self) -> list[GroupSearch]:
        stmt = select(GroupSearch).order_by(GroupSearch.id)
        return list(self.session.scalars(stmt).all())

    def get_group_search_by_id(self, search_id: int) -> GroupSearch | None:
        return self.session.get(GroupSearch, search_id)

    def pause_group_search(self, search: GroupSearch) -> None:
        search.is_active = False
        self.session.add(search)
        self.session.commit()

    def resume_group_search(self, search: GroupSearch) -> None:
        search.is_active = True
        self.session.add(search)
        self.session.commit()

    def delete_group_search(self, search: GroupSearch) -> None:
        self.session.delete(search)
        self.session.commit()

    def update_last_seen(self, search: GroupSearch, external_id: str) -> None:
        search.last_seen_external_id = external_id
        self.session.add(search)
        self.session.commit()


class BroadcastRepository:
    """Tracks which listings have already been broadcast to the group forum.

    Uses insert-ignore semantics so that the first caller wins and subsequent
    attempts for the same ``external_id`` are silently skipped.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def mark_sent(self, external_id: str) -> bool:
        """Insert *external_id* into broadcast_sent.

        Returns True if the row was newly inserted (first time seen),
        False if it already existed (duplicate — should be skipped).
        """
        row = BroadcastSent(external_id=external_id, sent_at=datetime.utcnow())
        try:
            self.session.add(row)
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
            return False

    def already_sent(self, external_id: str) -> bool:
        """Return True if *external_id* is already in broadcast_sent."""
        return self.session.get(BroadcastSent, external_id) is not None


class SubscriptionRepository:
    """Paid search-slot plans (one row per user, replace-on-purchase)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self, user_id: int) -> Subscription | None:
        sub = self.session.get(Subscription, user_id)
        if sub is None:
            return None
        if sub.expires_at <= datetime.utcnow():
            return None
        return sub

    def set_plan(self, user_id: int, plan: str, extra_searches: int, days: int = 30) -> Subscription:
        """Set/replace the user's plan (old plan is discarded, no stacking)."""
        now = datetime.utcnow()
        sub = self.session.get(Subscription, user_id)
        if sub is None:
            sub = Subscription(user_id=user_id, plan=plan, extra_searches=extra_searches,
                               purchased_at=now, expires_at=now + timedelta(days=days))
            self.session.add(sub)
        else:
            sub.plan = plan
            sub.extra_searches = extra_searches
            sub.purchased_at = now
            sub.expires_at = now + timedelta(days=days)
        self.session.commit()
        self.session.refresh(sub)
        return sub

    def active_search_limit(self, user_id: int) -> int:
        """Total allowed active searches: trial (1) or paid plan slots + referral bonus."""
        base = 1 if TrialRepository(self.session).is_active(user_id) else 0
        sub = self.get_active(user_id)
        referral_bonus = ReferralRepository(self.session).bonus_slots(user_id)
        return base + (sub.extra_searches if sub else 0) + referral_bonus


class TrialRepository:
    """30-day free trial (1 search) starting at the user's first contact."""

    TRIAL_DAYS = 30

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_start(self, user_id: int) -> Trial:
        trial = self.session.get(Trial, user_id)
        if trial is None:
            now = datetime.utcnow()
            trial = Trial(
                user_id=user_id,
                started_at=now,
                expires_at=now + timedelta(days=self.TRIAL_DAYS),
            )
            self.session.add(trial)
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                trial = self.session.get(Trial, user_id)
        return trial

    def is_active(self, user_id: int) -> bool:
        trial = self.get_or_start(user_id)
        return trial.expires_at > datetime.utcnow()

    def days_left(self, user_id: int) -> int:
        trial = self.get_or_start(user_id)
        return max(0, (trial.expires_at - datetime.utcnow()).days)


class ReferralRepository:
    """Invite-a-friend bonus slots: +1 slot for 30 days per credited invitee."""

    MAX_BONUS = 10  # anti-abuse cap on referral slots
    BONUS_DAYS = 30

    def __init__(self, session: Session) -> None:
        self.session = session

    def bonus_slots(self, referrer_id: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self.BONUS_DAYS)
        count = (
            self.session.query(Referral)
            .filter(Referral.referrer_id == referrer_id, Referral.created_at > cutoff)
            .count()
        )
        return min(count, self.MAX_BONUS)

    def is_known_user(self, user_id: int) -> bool:
        """A user is 'known' if they have settings, searches, or were already referred."""
        if self.session.get(UserSettings, user_id) is not None:
            return True
        if self.session.get(Referral, user_id) is not None:
            return True
        has_search = (
            self.session.query(Search.id).filter(Search.user_id == user_id).first()
        )
        return has_search is not None

    def credit(self, referrer_id: int, invitee_id: int) -> bool:
        """Credit *referrer_id* for inviting *invitee_id*. Returns True if credited."""
        if referrer_id == invitee_id:
            return False
        if self.is_known_user(invitee_id):
            return False
        try:
            self.session.add(Referral(invitee_id=invitee_id, referrer_id=referrer_id))
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
            return False
