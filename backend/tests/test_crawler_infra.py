"""Plan 1 — TimeBudget + CrawlCache 기본 동작 검증."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.services.crawlers import CrawlCache, TimeBudget, TimeBudgetExpired
from app.services.crawlers.crawl_cache import compute_key


def test_time_budget_remaining_decreases():
    tb = TimeBudget(total=1.0)
    r0 = tb.remaining()
    time.sleep(0.05)
    r1 = tb.remaining()
    assert r0 > r1
    assert tb.total == 1.0


def test_time_budget_expires():
    tb = TimeBudget(total=0.01)
    time.sleep(0.15)
    assert tb.expired() is True
    with pytest.raises(TimeBudgetExpired):
        tb.check()


def test_time_budget_sub_clamps_and_respects_remaining():
    tb = TimeBudget(total=2.0)
    sub = tb.sub(0.5)
    assert 0.0 <= sub <= 1.0
    # fraction out of range clamped
    assert tb.sub(-0.1) == 0.0
    assert tb.sub(2.0) <= tb.remaining()


def test_compute_key_stable_for_same_input():
    k1 = compute_key("취득세 감면", ["board_a", "board_b"], ["q1", "q2"])
    k2 = compute_key("취득세 감면", ["board_b", "board_a"], ["q2", "q1"])
    # 내부 정렬로 순서 무관
    assert k1 == k2


def test_compute_key_differs_for_different_input():
    k1 = compute_key("취득세", ["x"], ["a"])
    k2 = compute_key("재산세", ["x"], ["a"])
    assert k1 != k2


def test_crawl_cache_roundtrip(tmp_path: Path):
    cache = CrawlCache(db_path=tmp_path / "c.db", ttl_sec=60.0, enabled=True)
    key = compute_key("q", ["b1"], [])
    assert cache.get(key) is None
    cache.set(key, {"hits": 3, "items": [{"id": "a"}]})
    got = cache.get(key)
    assert got == {"hits": 3, "items": [{"id": "a"}]}


def test_crawl_cache_respects_ttl(tmp_path: Path):
    cache = CrawlCache(db_path=tmp_path / "c.db", ttl_sec=0.01, enabled=True)
    cache.set("k", {"v": 1})
    time.sleep(0.2)
    assert cache.get("k") is None


def test_crawl_cache_disabled_is_noop(tmp_path: Path):
    cache = CrawlCache(db_path=tmp_path / "c.db", ttl_sec=60.0, enabled=False)
    cache.set("k", {"v": 1})
    assert cache.get("k") is None


def test_crawl_cache_purge(tmp_path: Path):
    cache = CrawlCache(db_path=tmp_path / "c.db", ttl_sec=60.0, enabled=True)
    cache.set("k1", 1)
    cache.set("k2", 2)
    # purge older than 0 → 전체 제거
    assert cache.purge(older_than_sec=0.0) == 2
    assert cache.get("k1") is None
