from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Delta, ProbePlan, RuntimeObservation


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

    def set_runtime_observation(self, observation: RuntimeObservation) -> None:
        self.set_json("runtime_observation", observation.to_dict())

    def get_runtime_observation(self) -> RuntimeObservation | None:
        raw = self.get_json("runtime_observation")
        if not isinstance(raw, dict):
            return None
        return RuntimeObservation.from_dict(raw)

    def set_probe_plan(self, plan: ProbePlan) -> None:
        self.set_json(f"probe_plan:{plan.plan_id}", plan.to_dict())
        self.set_json("latest_probe_plan", {"plan_id": plan.plan_id})

    def get_probe_plan(self, plan_id: str) -> ProbePlan | None:
        raw = self.get_json(f"probe_plan:{plan_id}")
        return ProbePlan.from_dict(raw) if isinstance(raw, dict) else None

    def get_latest_probe_plan(self) -> ProbePlan | None:
        raw = self.get_json("latest_probe_plan")
        if not isinstance(raw, dict) or not raw.get("plan_id"):
            return None
        return self.get_probe_plan(str(raw["plan_id"]))

    def approve_probe_plan(self, plan_id: str, approved_by: str) -> None:
        self.set_json(f"probe_approval:{plan_id}", {"approved": True, "approved_by": approved_by})

    def get_probe_approval(self, plan_id: str) -> dict[str, object] | None:
        raw = self.get_json(f"probe_approval:{plan_id}")
        return raw if isinstance(raw, dict) else None
