"""Unit tests for app.observability.timing — decorator, context manager, quality_metric."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.observability import quality_metric, set_metrics_root, stage_timed


@pytest.fixture(autouse=True)
def _isolate_metrics(tmp_path: Path, monkeypatch):
    set_metrics_root(tmp_path)
    monkeypatch.setenv("OBS_METRICS_ROOT", str(tmp_path))
    yield
    set_metrics_root(None)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── 1. 동기 함수 데코레이터 ──
def test_decorator_sync_emits_pipeline_record(tmp_path: Path):
    @stage_timed("ranking")
    def work(n: int) -> int:
        return n * 2

    assert work(3) == 6

    records = _read_jsonl(tmp_path / "pipeline.jsonl")
    assert len(records) == 1
    rec = records[0]
    assert rec["stage"] == "ranking"
    assert rec["status"] == "ok"
    assert isinstance(rec["duration_ms"], int)
    assert rec["duration_ms"] >= 0
    assert "req_id" in rec


# ── 2. 비동기 함수 데코레이터 ──
def test_decorator_async_emits_pipeline_record(tmp_path: Path):
    @stage_timed("crawling")
    async def work(x: int) -> int:
        await asyncio.sleep(0)
        return x + 1

    result = asyncio.run(work(41))
    assert result == 42

    records = _read_jsonl(tmp_path / "pipeline.jsonl")
    assert len(records) == 1
    assert records[0]["stage"] == "crawling"
    assert records[0]["status"] == "ok"


# ── 3. 예외 경로는 status 필드에 에러 타입을 기록 ──
def test_decorator_async_error_records_status(tmp_path: Path):
    @stage_timed("drafting")
    async def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        asyncio.run(boom())

    records = _read_jsonl(tmp_path / "pipeline.jsonl")
    assert len(records) == 1
    assert records[0]["stage"] == "drafting"
    assert records[0]["status"] == "error:ValueError"


# ── 4. async 컨텍스트 매니저 + mark_status ──
def test_async_context_manager_with_mark_status(tmp_path: Path):
    async def run() -> None:
        async with stage_timed("crawling", req_id="rq-1") as t:
            t.mark_status("cache_hit")
            await asyncio.sleep(0)

    asyncio.run(run())

    records = _read_jsonl(tmp_path / "pipeline.jsonl")
    assert len(records) == 1
    assert records[0]["stage"] == "crawling"
    assert records[0]["status"] == "cache_hit"
    assert records[0]["req_id"] == "rq-1"


# ── 5. quality_metric emit ──
def test_quality_metric_writes_expected_fields(tmp_path: Path):
    quality_metric(
        req_id="rq-42",
        verified_citation_rate=0.83,
        hallucination_rate=None,
        revision_triggered=True,
        revision_rounds=1,
        confidence_tier="high",
        overall_confidence=0.78,
        golden_set_id="Q-003",
    )

    records = _read_jsonl(tmp_path / "quality.jsonl")
    assert len(records) == 1
    rec = records[0]
    assert rec["req_id"] == "rq-42"
    assert rec["verified_citation_rate"] == 0.83
    assert rec["hallucination_rate"] is None
    assert rec["confidence_tier"] == "high"
    assert rec["golden_set_id"] == "Q-003"


# ── 6. 다건 append 순서 보존 ──
def test_pipeline_records_append_in_order(tmp_path: Path):
    async def run() -> None:
        async with stage_timed("search_planning", req_id="rid"):
            pass
        async with stage_timed("crawling", req_id="rid"):
            pass
        async with stage_timed("ranking", req_id="rid"):
            pass

    asyncio.run(run())

    records = _read_jsonl(tmp_path / "pipeline.jsonl")
    stages = [r["stage"] for r in records]
    assert stages == ["search_planning", "crawling", "ranking"]
    assert all(r["req_id"] == "rid" for r in records)
