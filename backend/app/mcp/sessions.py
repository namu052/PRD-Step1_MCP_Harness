"""Plan 4 — SessionStore 추상화.

현재 `backend/mcp_server.py:_MCPSession` 은 모듈 전역 dict 5개 + TTL 300s 로
캐시한다. 프로세스 재시작 시 소실, 멀티 프로세스 미지원.

이 모듈은 두 구현을 제공한다:

1. `InMemoryStore` — 기존 `_MCPSession` 와 동등 (dict + TTL 300s)
2. `SqliteStore`  — 영속 백엔드 (`backend/data/mcp_session.db`). 프로세스 재시작 생존

선택은 `feature_flags.session_store` (`"memory"` | `"sqlite"`) 로 이뤄지며,
PR#2 에서 `mcp_server.py` 가 `get_session_store()` 로 교체된다.

행동 변경 없음 — 현재 `mcp_server.py` 는 여전히 자체 `_MCPSession` 을 쓴다.
이 모듈은 **infra 도입** 만 한다.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any, Iterator, Optional, Protocol, runtime_checkable


_DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "mcp_session.db"
_DEFAULT_TTL_SEC = 300.0  # 기존 _MCPSession.CACHE_TTL 과 동일
_SCHEMA_VERSION = 1

# 사전 정의 버킷 이름 — tools/pipelines 가 오타 없이 참조하도록 상수화
BUCKET_CRAWL = "crawl"
BUCKET_RANKED = "ranked"
BUCKET_EVIDENCE = "evidence"


@runtime_checkable
class SessionStore(Protocol):
    """세션 캐시 공통 인터페이스.

    버킷은 `BUCKET_*` 상수(crawl/ranked/evidence)를 사용한다.
    값은 JSON-직렬화 가능한 객체 또는 임의 파이썬 객체 (InMemory 한정).
    """

    def get(self, bucket: str, key: str) -> Optional[Any]: ...

    def set(self, bucket: str, key: str, value: Any) -> None: ...

    def iter_values(self, bucket: str) -> Iterator[Any]: ...

    def clear(self) -> None: ...


# ══════════════════════════════════════════════
# InMemoryStore — 기존 _MCPSession 과 동등
# ══════════════════════════════════════════════
class InMemoryStore:
    """dict + TTL 기반 세션 스토어. thread-safe via Lock.

    버킷별 dict + `(bucket, key) -> ts` 타임스탬프 테이블로 TTL 관리.
    TTL 만료 시 `get` 호출이 None 을 반환하며 레이지 삭제.

    임의 파이썬 객체 저장 가능 — 직렬화 없음.
    """

    def __init__(self, ttl_sec: float = _DEFAULT_TTL_SEC) -> None:
        self.ttl_sec = float(ttl_sec)
        self._buckets: dict[str, dict[str, Any]] = {}
        self._timestamps: dict[tuple[str, str], float] = {}
        self._lock = Lock()

    def _is_valid(self, bucket: str, key: str) -> bool:
        ts = self._timestamps.get((bucket, key))
        if ts is None:
            return False
        return (time.time() - ts) < self.ttl_sec

    def get(self, bucket: str, key: str) -> Optional[Any]:
        with self._lock:
            if not self._is_valid(bucket, key):
                self._drop_locked(bucket, key)
                return None
            return self._buckets.get(bucket, {}).get(key)

    def set(self, bucket: str, key: str, value: Any) -> None:
        with self._lock:
            self._buckets.setdefault(bucket, {})[key] = value
            self._timestamps[(bucket, key)] = time.time()

    def iter_values(self, bucket: str) -> Iterator[Any]:
        # 유효한 엔트리만 (만료된 것은 lazy drop)
        with self._lock:
            items = list(self._buckets.get(bucket, {}).items())
        for key, value in items:
            if self._is_valid(bucket, key):
                yield value

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._timestamps.clear()

    def _drop_locked(self, bucket: str, key: str) -> None:
        self._buckets.get(bucket, {}).pop(key, None)
        self._timestamps.pop((bucket, key), None)


# ══════════════════════════════════════════════
# SqliteStore — 영속 백엔드
# ══════════════════════════════════════════════
class SqliteStore:
    """SQLite 기반 영속 세션 스토어. 프로세스 재시작 생존.

    스키마:
      session_kv(bucket TEXT, k TEXT, v TEXT, created_at REAL, schema INTEGER,
                 PRIMARY KEY(bucket, k))

    값은 JSON 으로 직렬화. pydantic/dataclass 는 호출측에서 dict 로 변환해 저장.
    `iter_values` 는 dict/list 원시값을 yield — 상위 레이어에서 필요시 모델 재조립.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        ttl_sec: float = _DEFAULT_TTL_SEC,
        *,
        enabled: bool = True,
    ) -> None:
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
                "CREATE TABLE IF NOT EXISTS session_kv ("
                " bucket TEXT NOT NULL,"
                " k TEXT NOT NULL,"
                " v TEXT NOT NULL,"
                " created_at REAL NOT NULL,"
                " schema INTEGER NOT NULL,"
                " PRIMARY KEY(bucket, k)"
                ")"
            )
            conn.commit()

    def get(self, bucket: str, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT v, created_at, schema FROM session_kv WHERE bucket=? AND k=?",
                (bucket, key),
            ).fetchone()
            if not row:
                return None
            v, created_at, schema = row
            if schema != _SCHEMA_VERSION:
                conn.execute(
                    "DELETE FROM session_kv WHERE bucket=? AND k=?", (bucket, key),
                )
                conn.commit()
                return None
            if time.time() - float(created_at) > self.ttl_sec:
                conn.execute(
                    "DELETE FROM session_kv WHERE bucket=? AND k=?", (bucket, key),
                )
                conn.commit()
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None

    def set(self, bucket: str, key: str, value: Any) -> None:
        if not self.enabled:
            return
        try:
            encoded = json.dumps(value, ensure_ascii=False, default=_json_default)
        except (TypeError, ValueError):
            # 직렬화 불가 시 침묵 스킵 — InMemoryStore 만 지원하는 객체 저장 시나리오
            return
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_kv (bucket, k, v, created_at, schema)"
                " VALUES (?, ?, ?, ?, ?)",
                (bucket, key, encoded, time.time(), _SCHEMA_VERSION),
            )
            conn.commit()

    def iter_values(self, bucket: str) -> Iterator[Any]:
        if not self.enabled:
            return
        cutoff = time.time() - self.ttl_sec
        with self._lock, sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT v, created_at, schema FROM session_kv WHERE bucket=?",
                (bucket,),
            ).fetchall()
        for v, created_at, schema in rows:
            if schema != _SCHEMA_VERSION:
                continue
            if float(created_at) < cutoff:
                continue
            try:
                yield json.loads(v)
            except json.JSONDecodeError:
                continue

    def clear(self) -> None:
        if not self.enabled:
            return
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM session_kv")
            conn.commit()


def _json_default(obj: Any) -> Any:
    """pydantic/dataclass 를 fallback 직렬화."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


# ══════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════
def get_session_store(
    kind: str | None = None,
    *,
    ttl_sec: float = _DEFAULT_TTL_SEC,
    db_path: Optional[Path] = None,
) -> SessionStore:
    """feature_flags.session_store 를 따라 스토어 인스턴스를 반환한다.

    `kind` 가 명시되면 flag 를 무시하고 그 값을 사용 (테스트용).
    """
    from app import feature_flags as _ff

    selected = kind if kind is not None else _ff.flags.session_store
    if selected == "sqlite":
        return SqliteStore(db_path=db_path, ttl_sec=ttl_sec)
    return InMemoryStore(ttl_sec=ttl_sec)


__all__ = [
    "SessionStore",
    "InMemoryStore",
    "SqliteStore",
    "get_session_store",
    "BUCKET_CRAWL",
    "BUCKET_RANKED",
    "BUCKET_EVIDENCE",
]
