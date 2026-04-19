"""domain_priors.py — 소스 타입별 가중치 YAML 로더.

회수 순서: 환경변수 `DOMAIN_PRIORS_PATH` > `backend/config/domain_priors.yml` > 내장 default.
YAML 미존재 또는 파싱 실패 시 default 를 사용(배포 안정성).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# 플랜 2 design-doc 02 — official_* > community > web
_DEFAULT_PRIORS: dict[str, float] = {
    "official_law": 1.20,
    "official_case": 1.10,
    "official_qna": 1.05,
    "community": 0.95,
    "web": 0.85,
    # 미식별/legacy
    "unknown": 1.0,
}

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "domain_priors.yml"


@lru_cache
def load_domain_priors() -> dict[str, float]:
    path_str = os.environ.get("DOMAIN_PRIORS_PATH")
    path = Path(path_str) if path_str else _CONFIG_PATH
    if not path.exists() or yaml is None:
        return dict(_DEFAULT_PRIORS)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return dict(_DEFAULT_PRIORS)
    priors = dict(_DEFAULT_PRIORS)
    priors.update({str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))})
    return priors


def prior_for(source_type: str | None) -> float:
    priors = load_domain_priors()
    if not source_type:
        return priors.get("unknown", 1.0)
    return priors.get(source_type, priors.get("unknown", 1.0))


def _reset_cache_for_tests() -> None:
    load_domain_priors.cache_clear()
