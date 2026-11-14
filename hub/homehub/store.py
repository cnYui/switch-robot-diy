"""The home's own database: one SQLite file on this computer.

messages  every MQTT message under home/# (topic, payload, time) - the raw record
devices   one row per device: kind, name, info, online status, last state, last seen
readings  numbers pulled out of messages (signal strength, weight, ...) for charts
commands  every command HomeHub sent, and who asked for it
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, topic TEXT NOT NULL, payload TEXT);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(ts);
CREATE INDEX IF NOT EXISTS messages_topic ON messages(topic, ts);
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY, kind TEXT, name TEXT, info TEXT, status TEXT, state TEXT,
    first_seen REAL, last_seen REAL);
CREATE TABLE IF NOT EXISTS readings (
    ts REAL NOT NULL, device TEXT NOT NULL, metric TEXT NOT NULL, value REAL);
CREATE INDEX IF NOT EXISTS readings_dm ON readings(device, metric, ts);
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, device TEXT, cmd TEXT, source TEXT);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            self._db.close()

    def _x(self, sql, args=()):
        with self._lock:
            return self._db.execute(sql, args)

    def _all(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    # ---------------------------------------------------------------- writes
    def add_message(self, topic: str, payload: str, ts: float | None = None) -> None:
        self._x("INSERT INTO messages(ts, topic, payload) VALUES (?,?,?)", (ts or time.time(), topic, payload))

    def touch_device(self, dev_id: str, ts: float | None = None, **fields) -> None:
        ts = ts or time.time()
        with self._lock:
            row = self._db.execute("SELECT id FROM devices WHERE id=?", (dev_id,)).fetchone()
            if row is None:
                self._db.execute("INSERT INTO devices(id, first_seen, last_seen) VALUES (?,?,?)", (dev_id, ts, ts))
            else:
                self._db.execute("UPDATE devices SET last_seen=? WHERE id=?", (ts, dev_id))
            for k, v in fields.items():
                if k not in ("kind", "name", "info", "status", "state"):
                    raise KeyError(k)
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                self._db.execute(f"UPDATE devices SET {k}=? WHERE id=?", (v, dev_id))

    def set_name(self, dev_id: str, name: str) -> bool:
        return self._x("UPDATE devices SET name=? WHERE id=?", (name, dev_id)).rowcount > 0

    def add_reading(self, dev_id: str, metric: str, value: float, ts: float | None = None) -> None:
        self._x("INSERT INTO readings(ts, device, metric, value) VALUES (?,?,?,?)",
                (ts or time.time(), dev_id, metric, float(value)))

    def add_command(self, dev_id: str, cmd: str, source: str) -> None:
        self._x("INSERT INTO commands(ts, device, cmd, source) VALUES (?,?,?,?)", (time.time(), dev_id, cmd, source))

    def prune(self, keep_days: int) -> int:
        if keep_days <= 0:
            return 0
        cut = time.time() - keep_days * 86400
        n = self._x("DELETE FROM messages WHERE ts < ?", (cut,)).rowcount
        self._x("DELETE FROM readings WHERE ts < ?", (cut,))
        return n

    # ---------------------------------------------------------------- reads
    def devices(self) -> list[dict]:
        out = []
        for r in self._all("SELECT * FROM devices ORDER BY kind, id"):
            for k in ("info", "state"):
                try:
                    r[k] = json.loads(r[k]) if r[k] else None
                except ValueError:
                    pass
            out.append(r)
        return out

    def device(self, dev_id: str) -> dict | None:
        return next((d for d in self.devices() if d["id"] == dev_id), None)

    def messages(self, device: str | None = None, limit: int = 100) -> list[dict]:
        if device:
            return self._all("SELECT * FROM messages WHERE topic LIKE ? ORDER BY id DESC LIMIT ?",
                             (f"home/{device}/%", limit))
        return self._all("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,))

    def readings(self, device: str, metric: str | None = None, since: float = 0, limit: int = 5000) -> list[dict]:
        if metric:
            return self._all("SELECT ts, metric, value FROM readings WHERE device=? AND metric=? AND ts>=? "
                             "ORDER BY ts DESC LIMIT ?", (device, metric, since, limit))
        return self._all("SELECT ts, metric, value FROM readings WHERE device=? AND ts>=? ORDER BY ts DESC LIMIT ?",
                         (device, since, limit))

    def commands(self, limit: int = 50) -> list[dict]:
        return self._all("SELECT * FROM commands ORDER BY id DESC LIMIT ?", (limit,))

    def stats(self) -> dict:
        n = self._all("SELECT COUNT(*) AS n FROM messages")[0]["n"]
        return {"db": str(self.path), "messages": n,
                "bytes": self.path.stat().st_size if self.path.exists() else 0}
