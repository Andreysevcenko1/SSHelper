from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)



def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
