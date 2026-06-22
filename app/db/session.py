import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base

logger = logging.getLogger(__name__)

# Columns that must exist in the searches table (name -> SQLite type)
_REQUIRED_SEARCH_COLUMNS: dict[str, str] = {
    "base_url": "TEXT",
    "filters_json": "TEXT",
    "effective_url": "TEXT",
}

# Columns that must exist in the user_settings table (name -> SQLite type)
_REQUIRED_USER_SETTINGS_COLUMNS: dict[str, str] = {
    "selected_language": "TEXT",
}


def _migrate_sqlite(engine) -> None:
    """Add any missing columns to existing SQLite tables without data loss."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(searches)"))
        existing = {row[1] for row in result}

        for col_name, col_type in _REQUIRED_SEARCH_COLUMNS.items():
            if col_name not in existing:
                logger.info("Migration: adding column '%s' to searches", col_name)
                conn.execute(text(f"ALTER TABLE searches ADD COLUMN {col_name} {col_type}"))

        # Ensure user_settings table exists with all required columns
        result = conn.execute(text("PRAGMA table_info(user_settings)"))
        us_existing = {row[1] for row in result}
        if not us_existing:
            # Table was just created by create_all; nothing to migrate.
            pass
        else:
            for col_name, col_type in _REQUIRED_USER_SETTINGS_COLUMNS.items():
                if col_name not in us_existing:
                    logger.info("Migration: adding column '%s' to user_settings", col_name)
                    conn.execute(
                        text(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}")
                    )

        # Ensure broadcast_sent table exists (created by create_all above, but
        # guard for databases that pre-date this migration).
        result = conn.execute(text("PRAGMA table_info(broadcast_sent)"))
        bs_existing = {row[1] for row in result}
        if not bs_existing:
            logger.info("Migration: creating broadcast_sent table")
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS broadcast_sent "
                "(external_id TEXT PRIMARY KEY NOT NULL, "
                "sent_at DATETIME NOT NULL)"
            ))

        # Ensure group_searches table exists (created by create_all above, but
        # guard for databases that pre-date this migration).
        result = conn.execute(text("PRAGMA table_info(group_searches)"))
        gs_existing = {row[1] for row in result}
        if not gs_existing:
            logger.info("Migration: creating group_searches table")
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS group_searches "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "
                "title TEXT NOT NULL, "
                "url TEXT NOT NULL, "
                "base_url TEXT, "
                "filters_json TEXT, "
                "effective_url TEXT, "
                "route_key TEXT NOT NULL DEFAULT 'other', "
                "is_active BOOLEAN NOT NULL DEFAULT 1, "
                "last_seen_external_id TEXT, "
                "created_at DATETIME NOT NULL)"
            ))

        conn.commit()


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)
    if database_url.startswith("sqlite"):
        _migrate_sqlite(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)



def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

