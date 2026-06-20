import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Search
from app.services.filters import (
    build_effective_url,
    filters_from_json,
    filters_to_json,
    normalize_filters,
)


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
    ) -> Search:
        search = Search(
            user_id=user_id,
            url=url,
            title=title,
            base_url=base_url,
            filters_json=filters_json,
            effective_url=effective_url,
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
