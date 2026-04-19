"""Stage timing + quality metric emitter.

JSONL 스키마는 design-doc 00-quality-latency-baseline.md 에 고정되어 있다.
이 모듈은 그 계약을 준수하는 writer + decorator + context manager 만 노출한다.

- `@stage_timed("crawling")` : 동기/비동기 함수 데코레이터
- `async with stage_timed("crawling", req_id=...)` : 블록 계측용 컨텍스트 매니저
- `quality_metric(req_id=..., **fields)` : 답변 1건당 1 line

출력 경로:
  <repo>/observability/metrics/pipeline.jsonl
  <repo>/observability/metrics/quality.jsonl
환경변수 `OBS_METRICS_ROOT` 로 오버라이드 가능 (테스트용).
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_PIPELINE_FILE = "pipeline.jsonl"
_QUALITY_FILE = "quality.jsonl"

_write_lock = threading.Lock()
_metrics_root: Path | None = None


def _default_root() -> Path:
    env = os.environ.get("OBS_METRICS_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "observability").exists() or (parent / "scripts").exists():
            return parent / "observability" / "metrics"
    return here.parents[3] / "observability" / "metrics"


def set_metrics_root(path: Path | str | None) -> None:
    """테스트에서 출력 경로를 임시로 바꾸기 위한 훅."""
    global _metrics_root
    _metrics_root = Path(path) if path else None


def _metrics_dir() -> Path:
    root = _metrics_root or _default_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_req_id() -> str:
    return uuid.uuid4().hex[:12]


def _append_jsonl(filename: str, record: dict[str, Any]) -> None:
    path = _metrics_dir() / filename
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    try:
        with _write_lock:
            with path.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
    except OSError as exc:
        logger.warning("metrics write failed (%s): %s", path, exc)


def _emit_pipeline(req_id: str, stage: str, duration_ms: int, status: str,
                    extra: dict[str, Any] | None = None) -> None:
    rec: dict[str, Any] = {
        "ts": _iso_now(),
        "req_id": req_id,
        "stage": stage,
        "duration_ms": duration_ms,
        "status": status,
    }
    if extra:
        rec.update(extra)
    _append_jsonl(_PIPELINE_FILE, rec)


def quality_metric(
    *,
    req_id: str,
    verified_citation_rate: float | None = None,
    hallucination_rate: float | None = None,
    coverage_score: float | None = None,
    revision_triggered: bool | None = None,
    revision_rounds: int | None = None,
    confidence_tier: str | None = None,
    overall_confidence: float | None = None,
    golden_set_id: str | None = None,
    **extra: Any,
) -> None:
    """Emit a quality.jsonl record for a single answer.

    design-doc 00 의 스키마를 따른다. None 필드는 스키마상 null 허용이므로 그대로 기록.
    """
    rec: dict[str, Any] = {
        "ts": _iso_now(),
        "req_id": req_id,
        "verified_citation_rate": verified_citation_rate,
        "hallucination_rate": hallucination_rate,
        "coverage_score": coverage_score,
        "revision_triggered": revision_triggered,
        "revision_rounds": revision_rounds,
        "confidence_tier": confidence_tier,
        "overall_confidence": overall_confidence,
    }
    if golden_set_id is not None:
        rec["golden_set_id"] = golden_set_id
    for k, v in extra.items():
        rec.setdefault(k, v)
    _append_jsonl(_QUALITY_FILE, rec)


F = TypeVar("F", bound=Callable[..., Any])


class _StageTimer:
    """Decorator + async context manager dual-use helper."""

    __slots__ = ("_stage", "_req_id", "_t0", "_status", "_extra")

    def __init__(self, stage: str, req_id: str | None = None) -> None:
        self._stage = stage
        self._req_id = req_id or new_req_id()
        self._t0 = 0.0
        self._status: str = "ok"
        self._extra: dict[str, Any] = {}

    # ── context manager interface ──
    def mark_status(self, status: str, **extra: Any) -> None:
        self._status = status
        if extra:
            self._extra.update(extra)

    async def __aenter__(self) -> "_StageTimer":
        self._t0 = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        duration_ms = int((time.perf_counter() - self._t0) * 1000)
        status = self._status if exc is None else f"error:{exc_type.__name__}"
        _emit_pipeline(self._req_id, self._stage, duration_ms, status, self._extra or None)
        return False  # do not suppress

    def __enter__(self) -> "_StageTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = int((time.perf_counter() - self._t0) * 1000)
        status = self._status if exc is None else f"error:{exc_type.__name__}"
        _emit_pipeline(self._req_id, self._stage, duration_ms, status, self._extra or None)
        return False

    # ── decorator interface ──
    def __call__(self, fn: F) -> F:
        stage = self._stage
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*args: Any, **kwargs: Any) -> Any:
                req_id = kwargs.pop("_req_id", None) or new_req_id()
                t0 = time.perf_counter()
                status = "ok"
                try:
                    return await fn(*args, **kwargs)
                except BaseException as exc:
                    status = f"error:{type(exc).__name__}"
                    raise
                finally:
                    duration_ms = int((time.perf_counter() - t0) * 1000)
                    _emit_pipeline(req_id, stage, duration_ms, status)

            return awrap  # type: ignore[return-value]

        @functools.wraps(fn)
        def swrap(*args: Any, **kwargs: Any) -> Any:
            req_id = kwargs.pop("_req_id", None) or new_req_id()
            t0 = time.perf_counter()
            status = "ok"
            try:
                return fn(*args, **kwargs)
            except BaseException as exc:
                status = f"error:{type(exc).__name__}"
                raise
            finally:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                _emit_pipeline(req_id, stage, duration_ms, status)

        return swrap  # type: ignore[return-value]


def stage_timed(stage: str, req_id: str | None = None) -> _StageTimer:
    """Stage 계측 헬퍼.

    - 데코레이터로 쓸 때: `@stage_timed("crawling")`
    - async 컨텍스트로 쓸 때: `async with stage_timed("crawling", req_id=rid) as t:`
    - 동기 컨텍스트로 쓸 때: `with stage_timed("ranking", req_id=rid) as t:`
    """
    return _StageTimer(stage, req_id)
