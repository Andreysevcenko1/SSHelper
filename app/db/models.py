from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    selected_language: Mapped[str | None] = mapped_column(String(8), nullable=True)


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="SS.lv search")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # Extended filter support
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_url: Mapped[str | None] = mapped_column(Text, nullable=True)
