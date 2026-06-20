from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Search


class SearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_search(self, user_id: int, url: str, title: str = "SS.lv search") -> Search:
        search = Search(user_id=user_id, url=url, title=title)
        self.session.add(search)
        self.session.commit()
        self.session.refresh(search)
        return search

    def get_active_searches(self) -> list[Search]:
        stmt = select(Search).where(Search.is_active.is_(True))
        return list(self.session.scalars(stmt).all())

    def update_last_seen(self, search: Search, external_id: str) -> None:
        search.last_seen_external_id = external_id
        self.session.add(search)
        self.session.commit()
