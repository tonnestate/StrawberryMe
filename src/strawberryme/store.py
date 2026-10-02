from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Delta


class Store:
    def __init__(self, root: Path) -> None:
        directory = root / ".strawberry"
        directory.mkdir(exist_ok=True)
        self.path = directory / "strawberry.db"
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def set_json(self, key: str, value: object) -> None:
        raw = json.dumps(value, sort_keys=True)
        with self._connect() as db:
            db.execute(
                "INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, raw),
            )

    def get_json(self, key: str) -> object | None:
        with self._connect() as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_delta(self, delta: Delta) -> None:
        self.set_json("future_delta", delta.to_dict())

    def get_delta(self) -> Delta | None:
        raw = self.get_json("future_delta")
        if not isinstance(raw, dict):
            return None
        return Delta(tuple(raw.get("add", [])), tuple(raw.get("remove", [])))
