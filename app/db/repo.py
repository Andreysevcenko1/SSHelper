from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Search


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
