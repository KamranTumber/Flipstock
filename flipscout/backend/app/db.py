from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().resolved_database_url
        _engine = create_engine(url, connect_args={"check_same_thread": False})

        if url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def _pragma(dbapi_conn, _record):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()

    return _engine


def set_engine(engine) -> None:
    """Used by tests to point at an in-memory database."""
    global _engine
    _engine = engine


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(get_engine())


def session_scope() -> Session:
    return Session(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s
