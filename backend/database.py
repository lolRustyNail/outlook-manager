import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "outlook_accounts.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ACCOUNT_MIGRATIONS = {
    "display_name": "VARCHAR(255)",
    "group_name": "VARCHAR(120)",
    "note": "TEXT",
    "auth_mode": "VARCHAR(40) DEFAULT 'manual_token'",
    "status_message": "TEXT",
    "last_check_at": "DATETIME",
    "last_sync_at": "DATETIME",
}


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_sqlite_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "accounts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("accounts")}

    with engine.begin() as connection:
        for column_name, ddl in ACCOUNT_MIGRATIONS.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE accounts ADD COLUMN {column_name} {ddl}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema()
