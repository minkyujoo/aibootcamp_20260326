"""AI 영업관리 포탈 SQLite 연결."""

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    raw = os.environ.get("AICRM_DB_PATH", "data/aicrm.db")
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve().as_posix()}"


engine = create_engine(
    database_url(),
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_sqlite_companies_dart_column() -> None:
    """기존 SQLite DB에 companies.dart_profile 컬럼이 없으면 추가(create_all은 컬럼 추가를 안 함)."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
        colnames = {r[1] for r in rows}
        if colnames and "dart_profile" not in colnames:
            conn.execute(text("ALTER TABLE companies ADD COLUMN dart_profile TEXT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
