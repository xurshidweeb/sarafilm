import os
import config
from .db import Database as SQLiteDatabase
from .postgres_db import PostgresDatabase

def Database(db_path: str = None, database_url: str = None):
    url = database_url or getattr(config, "DATABASE_URL", None) or os.getenv("DATABASE_URL", "")
    if url and (url.startswith("postgres://") or url.startswith("postgresql://")):
        return PostgresDatabase(url)
    return SQLiteDatabase(db_path or getattr(config, "DATABASE_PATH", "bot_database.sqlite3"))

__all__ = ["Database", "SQLiteDatabase", "PostgresDatabase"]
