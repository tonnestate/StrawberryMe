from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import Delta, ProbePlan, RuntimeObservation

_HISTORY_LIMIT = 200


class Store:
    def __init__(self, root: Path) -> None:
        directory = root / ".strawberry"
        directory.mkdir(exist_ok=True)
        ignore = directory / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        self.path = directory / "strawberry.db"
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS file_map_cache (
                    path TEXT NOT NULL, parser_version TEXT NOT NULL, mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(path, parser_version)
                );
                CREATE TABLE IF NOT EXISTS evidence_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, run_id TEXT NOT NULL,
                    source_snapshot TEXT, provider_id TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS verification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                    source_snapshot TEXT, payload TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path)) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _trim(self, db: sqlite3.Connection, table: str) -> None:
        db.execute(
            f"DELETE FROM {table} WHERE id NOT IN (SELECT id FROM {table} ORDER BY id DESC LIMIT ?)",
            (_HISTORY_LIMIT,),
        )

    def set_json(self, key: str, value: object) -> None:
        raw = json.dumps(value, sort_keys=True)
        with self._db() as db:
            db.execute(
                "INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, raw),
            )

    def get_json(self, key: str) -> object | None:
        with self._db() as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_delta(self, delta: Delta) -> None:
        self.set_json("future_delta", delta.to_dict())

    def get_delta(self) -> Delta | None:
        raw = self.get_json("future_delta")
        return Delta(tuple(raw.get("add", [])), tuple(raw.get("remove", []))) if isinstance(raw, dict) else None

    def set_runtime_observation(self, observation: RuntimeObservation) -> None:
        self.set_json("runtime_observation", observation.to_dict())
        with self._db() as db:
            db.execute(
                "INSERT INTO evidence_history(created_at,run_id,source_snapshot,provider_id,payload) VALUES(?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), observation.run_id, observation.source.snapshot_id,
                 observation.provider_id, json.dumps(observation.to_dict(), sort_keys=True)),
            )
            self._trim(db, "evidence_history")

    def get_runtime_observation(self) -> RuntimeObservation | None:
        raw = self.get_json("runtime_observation")
        return RuntimeObservation.from_dict(raw) if isinstance(raw, dict) else None

    def evidence_history(self, limit: int = 10) -> list[RuntimeObservation]:
        with self._db() as db:
            rows = db.execute(
                "SELECT payload FROM evidence_history ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
        return [RuntimeObservation.from_dict(json.loads(row[0])) for row in rows]

    def append_verification(self, record: dict) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO verification_history(created_at,source_snapshot,payload) VALUES(?,?,?)",
                (datetime.now(timezone.utc).isoformat(), record.get("source_snapshot"), json.dumps(record, sort_keys=True)),
            )
            self._trim(db, "verification_history")

    def verification_history(self, limit: int = 10) -> list[dict]:
        with self._db() as db:
            rows = db.execute(
                "SELECT payload FROM verification_history ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
        return [raw for row in rows if isinstance((raw := json.loads(row[0])), dict)]

    def get_file_cache(self, path: str, parser_version: str, mtime_ns: int, size: int) -> dict | None:
        with self._db() as db:
            row = db.execute(
                "SELECT payload,mtime_ns,size FROM file_map_cache WHERE path=? AND parser_version=?", (path, parser_version)
            ).fetchone()
        if not row or int(row[1]) != int(mtime_ns) or int(row[2]) != int(size):
            return None
        raw = json.loads(row[0])
        return raw if isinstance(raw, dict) else None

    def set_file_cache(self, path: str, parser_version: str, mtime_ns: int, size: int, payload: dict) -> None:
        with self._db() as db:
            db.execute(
                """INSERT INTO file_map_cache(path,parser_version,mtime_ns,size,payload) VALUES(?,?,?,?,?)
                   ON CONFLICT(path,parser_version) DO UPDATE SET mtime_ns=excluded.mtime_ns,size=excluded.size,payload=excluded.payload""",
                (path, parser_version, int(mtime_ns), int(size), json.dumps(payload, sort_keys=True)),
            )

    def prune_file_cache(self, current_paths: set[str], parser_version: str) -> None:
        with self._db() as db:
            rows = db.execute("SELECT path FROM file_map_cache WHERE parser_version=?", (parser_version,)).fetchall()
            stale = [(row[0], parser_version) for row in rows if row[0] not in current_paths]
            db.executemany("DELETE FROM file_map_cache WHERE path=? AND parser_version=?", stale)

    def set_probe_plan(self, plan: ProbePlan) -> None:
        self.set_json(f"probe_plan:{plan.plan_id}", plan.to_dict())
        self.set_json("latest_probe_plan", plan.to_dict())

    def get_probe_plan(self, plan_id: str) -> ProbePlan | None:
        raw = self.get_json(f"probe_plan:{plan_id}")
        return ProbePlan.from_dict(raw) if isinstance(raw, dict) else None

    def get_latest_probe_plan(self) -> ProbePlan | None:
        raw = self.get_json("latest_probe_plan")
        return ProbePlan.from_dict(raw) if isinstance(raw, dict) else None

    def approve_probe_plan(self, plan_id: str, approved_by: str) -> None:
        self.set_json(f"probe_approval:{plan_id}", {"approved": True, "approved_by": approved_by})

    def get_probe_approval(self, plan_id: str) -> dict | None:
        raw = self.get_json(f"probe_approval:{plan_id}")
        return raw if isinstance(raw, dict) else None
