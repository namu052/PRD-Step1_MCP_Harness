"""Plan 4 PR#1 — SessionStore (InMemory + Sqlite + factory)."""
from __future__ import annotations

import os
import time

import pytest

from app import feature_flags as ff
from app.mcp.sessions import (
    BUCKET_CRAWL,
    BUCKET_EVIDENCE,
    BUCKET_RANKED,
    InMemoryStore,
    SqliteStore,
    get_session_store,
)


@pytest.fixture(autouse=True)
def _restore_env():
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)
    ff._reload_for_tests()


# ── InMemoryStore ───────────────────────────────────────────────────

def test_inmemory_get_set_roundtrip():
    store = InMemoryStore(ttl_sec=60)
    store.set(BUCKET_CRAWL, "q1", [{"id": "law_1"}])
    assert store.get(BUCKET_CRAWL, "q1") == [{"id": "law_1"}]
    assert store.get(BUCKET_CRAWL, "missing") is None


def test_inmemory_ttl_expiry():
    store = InMemoryStore(ttl_sec=0.01)
    store.set(BUCKET_RANKED, "q", ["a", "b"])
    time.sleep(0.15)
    assert store.get(BUCKET_RANKED, "q") is None


def test_inmemory_iter_values_skips_expired():
    store = InMemoryStore(ttl_sec=0.05)
    store.set(BUCKET_EVIDENCE, "k1", {"slot": 1})
    time.sleep(0.2)
    store.set(BUCKET_EVIDENCE, "k2", {"slot": 2})
    alive = list(store.iter_values(BUCKET_EVIDENCE))
    assert alive == [{"slot": 2}]


def test_inmemory_clear_wipes_all_buckets():
    store = InMemoryStore(ttl_sec=60)
    store.set(BUCKET_CRAWL, "a", 1)
    store.set(BUCKET_RANKED, "b", 2)
    store.clear()
    assert store.get(BUCKET_CRAWL, "a") is None
    assert store.get(BUCKET_RANKED, "b") is None


def test_inmemory_accepts_arbitrary_python_objects():
    """직렬화 불가 객체도 InMemory 는 그대로 저장 (find_by_source_id 지원)."""

    class Marker:
        def __init__(self, v: int) -> None:
            self.v = v

    store = InMemoryStore(ttl_sec=60)
    m = Marker(7)
    store.set(BUCKET_RANKED, "q", [m])
    got = store.get(BUCKET_RANKED, "q")
    assert got[0].v == 7


# ── SqliteStore ─────────────────────────────────────────────────────

def test_sqlite_roundtrip_survives_new_instance(tmp_path):
    db = tmp_path / "sess.db"
    s1 = SqliteStore(db_path=db, ttl_sec=60)
    s1.set(BUCKET_CRAWL, "q1", [{"id": "law_1"}, {"id": "law_2"}])
    # 새 인스턴스 — 같은 파일 읽기
    s2 = SqliteStore(db_path=db, ttl_sec=60)
    assert s2.get(BUCKET_CRAWL, "q1") == [{"id": "law_1"}, {"id": "law_2"}]


def test_sqlite_ttl_expiry(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=0.01)
    s.set(BUCKET_CRAWL, "q", {"x": 1})
    time.sleep(0.15)
    assert s.get(BUCKET_CRAWL, "q") is None


def test_sqlite_bucket_isolation(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60)
    s.set(BUCKET_CRAWL, "k", "A")
    s.set(BUCKET_RANKED, "k", "B")
    assert s.get(BUCKET_CRAWL, "k") == "A"
    assert s.get(BUCKET_RANKED, "k") == "B"


def test_sqlite_iter_values(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60)
    s.set(BUCKET_EVIDENCE, "k1", {"i": 1})
    s.set(BUCKET_EVIDENCE, "k2", {"i": 2})
    values = sorted(list(s.iter_values(BUCKET_EVIDENCE)), key=lambda d: d["i"])
    assert values == [{"i": 1}, {"i": 2}]


def test_sqlite_clear(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60)
    s.set(BUCKET_CRAWL, "q", [1, 2])
    s.clear()
    assert s.get(BUCKET_CRAWL, "q") is None


def test_sqlite_disabled_is_noop(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60, enabled=False)
    s.set(BUCKET_CRAWL, "q", [1])
    assert s.get(BUCKET_CRAWL, "q") is None
    assert list(s.iter_values(BUCKET_CRAWL)) == []


def test_sqlite_skips_unserializable_value(tmp_path):
    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60)

    class NotJson:
        __slots__ = ("a",)

        def __init__(self):
            self.a = 1

    # fallback default 로 __dict__ 가 없어 저장 실패 → 침묵 스킵
    s.set(BUCKET_CRAWL, "q", NotJson())
    assert s.get(BUCKET_CRAWL, "q") is None


def test_sqlite_serializes_pydantic_via_default(tmp_path):
    from pydantic import BaseModel

    class M(BaseModel):
        id: str
        score: float

    db = tmp_path / "sess.db"
    s = SqliteStore(db_path=db, ttl_sec=60)
    s.set(BUCKET_RANKED, "q", [M(id="x", score=0.9)])
    got = s.get(BUCKET_RANKED, "q")
    assert got == [{"id": "x", "score": 0.9}]


# ── Factory ─────────────────────────────────────────────────────────

def test_factory_default_flag_memory():
    os.environ.pop("SESSION_STORE", None)
    ff._reload_for_tests()
    store = get_session_store()
    assert isinstance(store, InMemoryStore)


def test_factory_sqlite_when_flag_set(tmp_path):
    os.environ["SESSION_STORE"] = "sqlite"
    ff._reload_for_tests()
    store = get_session_store(db_path=tmp_path / "f.db")
    assert isinstance(store, SqliteStore)


def test_factory_kind_overrides_flag(tmp_path):
    os.environ["SESSION_STORE"] = "sqlite"
    ff._reload_for_tests()
    store = get_session_store(kind="memory")
    assert isinstance(store, InMemoryStore)
