"""crawl_cache.py — Plan 1 SQLite 영속 캐시 (프로세스 재시작 생존).

키 = `(question_hash, priority_boards_hash, search_queries_hash)` 조합의 SHA256.
TTL 기본 1h (feature_flags.crawl_cache_ttl_sec). Hit 시 JSON 역직렬화.

임의의 직렬화 가능 객체를 저장 — 크롤 결과 list[dict] 를 직접 넣는다.
스키마 변경 시 `_SCHEMA_VERSION` 업데이트 + 자동 재생성.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any, Optional

_SCHEMA_VERSION = 1
_DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "crawl_cache.db"


def _canonical(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return "[" + ",".join(_canonical(v) for v in sorted(map(str, value))) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{k}:{_canonical(v)}" for k, v in sorted(value.items())
        ) + "}"
    return str(value)


def compute_key(*parts: Any) -> str:
    blob = "|".join(_canonical(p) for p in parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class CrawlCache:
    """간단한 SQLite 기반 KV 캐시. thread-safe via Lock.

    `enabled=False` 면 get/set 이 no-op (feature_flags.crawl_cache_enabled=False).
    """

    def __init__(self, db_path: Optional[Path] = None, ttl_sec: float = 3600.0, *, enabled: bool = True):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.ttl_sec = float(ttl_sec)
        self.enabled = bool(enabled)
        self._lock = Lock()
        if self.enabled:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                " k TEXT PRIMARY KEY,"
                " v TEXT NOT NULL,"
                " created_at REAL NOT NULL,"
                " schema INTEGER NOT NULL"
                ")"
            )
            conn.commit()

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT v, created_at, schema FROM kv WHERE k = ?", (key,)
            ).fetchone()
            if not row:
                return None
            v, created_at, schema = row
            if schema != _SCHEMA_VERSION:
                conn.execute("DELETE FROM kv WHERE k = ?", (key,))
                conn.commit()
                return None
            if time.time() - float(created_at) > self.ttl_sec:
                conn.execute("DELETE FROM kv WHERE k = ?", (key,))
                conn.commit()
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv (k, v, created_at, schema) VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), time.time(), _SCHEMA_VERSION),
            )
            conn.commit()

    def purge(self, older_than_sec: float | None = None) -> int:
        if not self.enabled:
            return 0
        cutoff = time.time() - (older_than_sec if older_than_sec is not None else self.ttl_sec)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM kv WHERE created_at < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
