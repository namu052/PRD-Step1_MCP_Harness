"""Plan 4 PR#1 — pipeline_events emit 훅."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import feature_flags as ff
from app.mcp import pipeline_events as pe


@pytest.fixture(autouse=True)
def _reset_env_and_root(tmp_path):
    before = dict(os.environ)
    pe.set_events_root(tmp_path)
    yield tmp_path
    pe.set_events_root(None)
    os.environ.clear()
    os.environ.update(before)
    ff._reload_for_tests()


def _read_events(root: Path) -> list[dict]:
    path = root / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_v1_suppresses_emit(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v1"
    ff._reload_for_tests()
    wrote = pe.emit("stage_started", req_id="r1", payload={"stage": "crawling"})
    assert wrote is False
    assert _read_events(root) == []


def test_v2_writes_jsonl(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    wrote = pe.emit("stage_started", req_id="r1", payload={"stage": "crawling"})
    assert wrote is True
    events = _read_events(root)
    assert len(events) == 1
    assert events[0]["type"] == "stage_started"
    assert events[0]["req_id"] == "r1"
    assert events[0]["payload"] == {"stage": "crawling"}
    assert "ts" in events[0]
    assert "mono" in events[0]


def test_unknown_event_type_skipped(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    assert pe.emit("not_a_real_event", req_id="r1") is False
    assert _read_events(root) == []


def test_stage_started_and_completed_helpers(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    pe.stage_started("r1", "crawling", total_queries=3)
    pe.stage_completed("r1", "crawling", duration_ms=1234, status="ok", hits=10)
    events = _read_events(root)
    assert len(events) == 2
    assert events[0]["type"] == "stage_started"
    assert events[0]["payload"]["stage"] == "crawling"
    assert events[0]["payload"]["total_queries"] == 3
    assert events[1]["type"] == "stage_completed"
    assert events[1]["payload"]["duration_ms"] == 1234
    assert events[1]["payload"]["status"] == "ok"
    assert events[1]["payload"]["hits"] == 10


def test_crawl_progress_board_helper(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    pe.crawl_progress_board("r1", board="질의응답", hits=5, cumulative=12)
    events = _read_events(root)
    assert events[0]["type"] == "crawl_progress_board"
    assert events[0]["payload"] == {"board": "질의응답", "hits": 5, "cumulative": 12}


def test_source_verified_helper_optional_score(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    pe.source_verified("r1", source_id="law_1", classification="official_law")
    pe.source_verified("r1", source_id="web_1", classification="web", score=0.42)
    events = _read_events(root)
    assert "score" not in events[0]["payload"]
    assert events[1]["payload"]["score"] == 0.42


def test_verification_partial_truncates_long_claim(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    long_claim = "가" * 500
    pe.verification_partial("r1", claim_index=0, claim=long_claim, status="supported")
    events = _read_events(root)
    # 200자 상한
    assert len(events[0]["payload"]["claim"]) == 200


def test_revision_events(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    pe.revision_started("r1", round_index=1)
    pe.revision_completed("r1", round_index=1, delta_confidence=0.08)
    pe.revision_completed("r1", round_index=2, delta_confidence=0.02, early_stopped=True)
    events = _read_events(root)
    assert events[0]["type"] == "revision_started"
    assert events[0]["payload"]["round"] == 1
    assert events[2]["payload"]["early_stopped"] is True
    assert events[2]["payload"]["delta_confidence"] == 0.02


def test_seq_field_optional(_reset_env_and_root):
    root = _reset_env_and_root
    os.environ["SSE_EVENTS_VERSION"] = "v2"
    ff._reload_for_tests()
    pe.emit("stage_started", req_id="r1", payload={"stage": "s"}, seq=3)
    events = _read_events(root)
    assert events[0]["seq"] == 3


def test_allowed_types_coverage():
    # 헬퍼가 내부적으로 사용하는 모든 타입이 허용 목록에 있음
    allowed = set(pe.iter_allowed_types())
    assert {
        "stage_started",
        "stage_completed",
        "crawl_progress_board",
        "source_verified",
        "verification_partial",
        "revision_started",
        "revision_completed",
        "pipeline_metric",
    } <= allowed
