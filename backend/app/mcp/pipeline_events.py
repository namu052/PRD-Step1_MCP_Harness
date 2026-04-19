"""Plan 4 — 진행형(pipeline) 이벤트 emit 훅.

Frontend 가 Stage 별로 즉시 표시할 수 있도록 파이프라인 도중 이벤트를 방출한다.
현재 저장 매체는 JSONL (`observability/metrics/events.jsonl`) — HTTP/SSE 전송은
PR#2+ 에서 `routers/chat_stream` 이 tail 방식으로 읽어 내보낸다.

게이트:
- `feature_flags.sse_events_version == "v2"` 일 때만 기록
- `v1` 이면 모든 emit 이 no-op → 기존 동작 보존

이벤트 타입 (payload 는 설계 문서 04-sse-progressive-events.md 참조):
- stage_started / stage_completed : 모든 Stage 1~6
- crawl_progress_board            : BBS 보드별 누적 hit
- source_verified                 : 단건 출처 검증 완료
- verification_partial            : claim 단위 supported/contradicted
- revision_started / revision_completed : revision 라운드 진행
- pipeline_metric                 : Stage 미분류 지표 (예: cache_hit_rate)

행동 변경 없음 — `mcp_server.py` 는 아직 이 모듈을 호출하지 않는다. 호출 주입은 PR#2.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal


logger = logging.getLogger(__name__)

# 허용 이벤트 타입 (오타 방지)
EventType = Literal[
    "stage_started",
    "stage_completed",
    "crawl_progress_board",
    "source_verified",
    "verification_partial",
    "revision_started",
    "revision_completed",
    "pipeline_metric",
]

_ALLOWED_TYPES: frozenset[str] = frozenset([
    "stage_started",
    "stage_completed",
    "crawl_progress_board",
    "source_verified",
    "verification_partial",
    "revision_started",
    "revision_completed",
    "pipeline_metric",
])

_EVENTS_FILE = "events.jsonl"
_write_lock = threading.Lock()
_events_root: Path | None = None


def set_events_root(path: Path | str | None) -> None:
    """테스트 출력 경로 오버라이드."""
    global _events_root
    _events_root = Path(path) if path else None


def _default_root() -> Path:
    env = os.environ.get("OBS_METRICS_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "observability").exists() or (parent / "scripts").exists():
            return parent / "observability" / "metrics"
    return here.parents[3] / "observability" / "metrics"


def _events_dir() -> Path:
    root = _events_root or _default_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _v2_enabled() -> bool:
    """feature_flags 재평가를 매 호출마다 수행 (테스트에서 reload 되는 케이스 지원)."""
    try:
        from app import feature_flags as _ff
        return _ff.flags.sse_events_version == "v2"
    except Exception:
        return False


def emit(
    event_type: str,
    *,
    req_id: str,
    payload: dict[str, Any] | None = None,
    seq: int | None = None,
) -> bool:
    """이벤트를 JSONL 로 append. v1 일 때는 no-op.

    Returns:
        True 면 기록됨, False 면 스킵(v1 또는 허용 타입 외).
    """
    if event_type not in _ALLOWED_TYPES:
        logger.warning("pipeline_events.emit: unknown event_type=%s — 스킵", event_type)
        return False
    if not _v2_enabled():
        return False
    rec: dict[str, Any] = {
        "ts": _iso_now(),
        "mono": time.monotonic(),
        "req_id": req_id,
        "type": event_type,
    }
    if seq is not None:
        rec["seq"] = int(seq)
    if payload:
        rec["payload"] = payload
    path = _events_dir() / _EVENTS_FILE
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
    try:
        with _write_lock:
            with path.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
    except OSError as exc:
        logger.warning("events write failed (%s): %s", path, exc)
        return False
    return True


# ── 편의 헬퍼들 ───────────────────────────────────────────────────────

def stage_started(req_id: str, stage: str, **extra: Any) -> bool:
    return emit("stage_started", req_id=req_id, payload={"stage": stage, **extra})


def stage_completed(
    req_id: str,
    stage: str,
    *,
    duration_ms: int | None = None,
    status: str = "ok",
    **extra: Any,
) -> bool:
    payload: dict[str, Any] = {"stage": stage, "status": status, **extra}
    if duration_ms is not None:
        payload["duration_ms"] = int(duration_ms)
    return emit("stage_completed", req_id=req_id, payload=payload)


def crawl_progress_board(
    req_id: str,
    *,
    board: str,
    hits: int,
    cumulative: int,
) -> bool:
    return emit(
        "crawl_progress_board",
        req_id=req_id,
        payload={"board": board, "hits": int(hits), "cumulative": int(cumulative)},
    )


def source_verified(
    req_id: str,
    *,
    source_id: str,
    classification: str,
    score: float | None = None,
) -> bool:
    payload: dict[str, Any] = {
        "source_id": source_id,
        "classification": classification,
    }
    if score is not None:
        payload["score"] = float(score)
    return emit("source_verified", req_id=req_id, payload=payload)


def verification_partial(
    req_id: str,
    *,
    claim_index: int,
    claim: str,
    status: str,
) -> bool:
    return emit(
        "verification_partial",
        req_id=req_id,
        payload={
            "claim_index": int(claim_index),
            "claim": claim[:200],
            "status": status,
        },
    )


def revision_started(req_id: str, *, round_index: int) -> bool:
    return emit(
        "revision_started",
        req_id=req_id,
        payload={"round": int(round_index)},
    )


def revision_completed(
    req_id: str,
    *,
    round_index: int,
    delta_confidence: float | None = None,
    early_stopped: bool = False,
) -> bool:
    payload: dict[str, Any] = {
        "round": int(round_index),
        "early_stopped": bool(early_stopped),
    }
    if delta_confidence is not None:
        payload["delta_confidence"] = float(delta_confidence)
    return emit("revision_completed", req_id=req_id, payload=payload)


def iter_allowed_types() -> Iterable[str]:
    return iter(_ALLOWED_TYPES)


__all__ = [
    "EventType",
    "emit",
    "set_events_root",
    "stage_started",
    "stage_completed",
    "crawl_progress_board",
    "source_verified",
    "verification_partial",
    "revision_started",
    "revision_completed",
    "iter_allowed_types",
]
