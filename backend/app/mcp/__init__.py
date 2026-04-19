"""Plan 4 — MCP modularization package.

이 패키지는 `backend/mcp_server.py` (1039줄, TD-0001) 를 단계적으로 분해한다.

PR#1 범위 (현재):
- `schemas.py`   : 9개 Tool 입력 pydantic 모델 통합
- `sessions.py`  : `SessionStore` 프로토콜 + `InMemoryStore` + `SqliteStore`
- `pipeline_events.py` : 진행형 SSE 이벤트 emit 훅 (JSONL, v2 게이트)

PR#2~ (이월, live MCP smoke 필요):
- `server.py`, `tools/*.py`, `pipelines.py` 로 facade 분할
- `mcp_server.py` ≤150줄 축소, FastMCP 데코레이터만 보유
- 파이프라인 각 Stage 에서 `pipeline_events.emit(...)` 호출점 삽입
- SESSION_STORE=sqlite 스위치 실 기동 검증

행동 변경 없음. 기존 `mcp_server.py` 는 그대로 동작한다.
"""
from __future__ import annotations

__all__ = ["schemas", "sessions", "pipeline_events"]
