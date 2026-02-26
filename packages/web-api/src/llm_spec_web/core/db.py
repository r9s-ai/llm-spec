"""Database wiring for llm-spec web service."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from llm_spec_web.config import settings

_url = make_url(settings.database_url)
_connect_args: dict[str, object] = {}
if _url.drivername.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    if _url.database:
        db_path = Path(_url.database)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url, future=True, pool_pre_ping=True, connect_args=_connect_args
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for DB session.

    Yields:
        Session: SQLAlchemy session instance.

    Example:
        ```python
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
        ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
