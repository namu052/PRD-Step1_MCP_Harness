"""feature_flags.py — dual-axis 고도화 공통 feature flag 레지스트리.

Plan 1~4의 회귀 방지용 토글을 **한 곳**에 집중한다.
회귀 발생 시 이 파일의 환경변수 한 줄 수정으로 전량 off가 가능하다.

전부 환경변수 기반 (프로세스 생애주기 내 고정). 런타임 변경이 필요한 A/B는
`feature_flags.yaml` + 쿠키 분기(Plan 4)로 확장 예정 — 현재는 env override.

사용 예:
    from app.feature_flags import flags
    if flags.retrieval_mode == "hybrid":
        ...
    sema = asyncio.Semaphore(flags.bbs_concurrency)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _env_str(key: str, default: str, allowed: tuple[str, ...] | None = None) -> str:
    v = os.environ.get(key, default)
    if allowed and v not in allowed:
        return default
    return v


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class FeatureFlags:
    # Plan 1 — crawler 동시성
    bbs_concurrency: int            # BBS query 병렬도 (1=직렬, default 4)
    bbs_page_pool: int              # Playwright 페이지 풀 크기 (default 4)
    crawl_cache_ttl_sec: int        # SQLite 영속 캐시 TTL (default 3600=1h)
    crawl_cache_enabled: bool       # SQLite 캐시 on/off
    crawl_time_budget_sec: float    # TimeBudget 전체 상한 (default 180s)

    # Plan 2 — retrieval
    retrieval_mode: str             # "embedding" | "hybrid" (default hybrid, 회귀 시 embedding)
    retrieval_alpha: float          # hybrid 가중 α * embed + (1-α) * bm25 (default 0.6)
    embedding_batch_size: int       # OpenAI embeddings 배치 크기 (default 32)
    searchplan_cache_ttl_sec: int   # SearchPlan LRU+SQLite TTL (default 86400=24h)
    searchplan_cache_enabled: bool

    # Plan 3 — verification
    confidence_tiers: str           # "v1" (3단계) | "v2" (5단계)
    max_revision_rounds: int        # 최대 revision 라운드 (default 2, 0=비활성)
    revision_stagnation_delta: float  # |Δconfidence| < 이 값이면 early stop
    verify_morph: bool              # 형태소 분석기 on/off (kiwipiepy)
    hallucination_bidirectional: bool  # 반방향 coverage_score 계산 on/off

    # Plan 4 — SSE / session store
    sse_events_version: str         # "v1" | "v2" (v2=progressive events)
    session_store: str              # "memory" | "sqlite"


@lru_cache
def _load() -> FeatureFlags:
    return FeatureFlags(
        bbs_concurrency=_env_int("BBS_CONCURRENCY", 4),
        bbs_page_pool=_env_int("BBS_PAGE_POOL", 4),
        crawl_cache_ttl_sec=_env_int("CRAWL_CACHE_TTL_SEC", 3600),
        crawl_cache_enabled=_env_bool("CRAWL_CACHE_ENABLED", True),
        crawl_time_budget_sec=_env_float("CRAWL_TIME_BUDGET_SEC", 180.0),
        retrieval_mode=_env_str("RETRIEVAL_MODE", "hybrid", ("embedding", "hybrid")),
        retrieval_alpha=_env_float("RETRIEVAL_ALPHA", 0.6),
        embedding_batch_size=_env_int("EMBEDDING_BATCH_SIZE", 32),
        searchplan_cache_ttl_sec=_env_int("SEARCHPLAN_CACHE_TTL_SEC", 86400),
        searchplan_cache_enabled=_env_bool("SEARCHPLAN_CACHE_ENABLED", True),
        confidence_tiers=_env_str("CONFIDENCE_TIERS", "v2", ("v1", "v2")),
        max_revision_rounds=_env_int("MAX_REVISION_ROUNDS", 2),
        revision_stagnation_delta=_env_float("REVISION_STAGNATION_DELTA", 0.05),
        verify_morph=_env_bool("VERIFY_MORPH", False),
        hallucination_bidirectional=_env_bool("HALLUCINATION_BIDIRECTIONAL", True),
        sse_events_version=_env_str("SSE_EVENTS_VERSION", "v2", ("v1", "v2")),
        session_store=_env_str("SESSION_STORE", "memory", ("memory", "sqlite")),
    )


def _reload_for_tests() -> FeatureFlags:
    global flags
    _load.cache_clear()
    flags = _load()
    return flags


flags: FeatureFlags = _load()


__all__ = ["FeatureFlags", "flags", "_reload_for_tests"]
