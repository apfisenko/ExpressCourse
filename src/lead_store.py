import asyncio
import logging
import sqlite3
from pathlib import Path

from langsmith import traceable

from src.config import Config

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS leads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    contact    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


class LeadStore:
    def __init__(self, config: Config) -> None:
        self._db_path = config.leads_db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)
            conn.commit()
        logging.info("LeadStore ready: %s", self._db_path)

    @traceable(name="capture_lead")
    async def capture(self, name: str, contact: str) -> dict:
        await asyncio.to_thread(self._insert, name, contact)
        logging.info("Lead captured: name=%r contact=%r", name, contact)
        return {"status": "ok", "message": f"Заявка от {name} ({contact}) сохранена."}

    def _insert(self, name: str, contact: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO leads (name, contact) VALUES (?, ?)",
                (name, contact),
            )
            conn.commit()
