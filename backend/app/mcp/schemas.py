"""Plan 4 — 9개 MCP Tool 입력 스키마 (pydantic v2).

FastMCP 는 타입 힌트로부터 자체 스키마를 생성하지만, 툴 간 **검증 일관성**과
향후 HTTP 노출/Frontend 계약을 위해 pydantic 입력 모델을 별도로 정의한다.

출력은 현재 모두 markdown `str` 이라 별도 모델이 필요 없지만, `ToolResult`
제네릭은 PR#2 이후 tools/* 로 분할될 때 확장 포인트로 남겨 둔다.

행동 변경 없음 — 이 모듈은 PR#2 에서 tools/* 가 임포트하여 사용한다.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class _ToolModel(BaseModel):
    """공통 base — extra=forbid 로 오타·예상치 못한 필드 차단."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ── Tool 1~3: 브라우저/로그인 제어 (인자 없음) ──────────────────────────

class CheckOltaLoginRequest(_ToolModel):
    """OLTA 로그인 상태 조회 (인자 없음)."""


class OpenOltaForLoginRequest(_ToolModel):
    """OLTA 로그인 브라우저 오픈 (인자 없음)."""


class CloseOltaBrowserRequest(_ToolModel):
    """OLTA 브라우저 종료 (인자 없음)."""


# ── Tool 4: 검색 계획 미리보기 ────────────────────────────────────────

class GetSearchPlanRequest(_ToolModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ── Tool 5: 브라우저에 HTML 답변 표시 ───────────────────────────────

class ShowAnswerInBrowserRequest(_ToolModel):
    html_content: str = Field(..., min_length=1)


# ── Tool 6: 캐시된 문서 본문 조회 ────────────────────────────────────

class GetDocumentContentRequest(_ToolModel):
    source_id: str = Field(..., min_length=1, max_length=200)


# ── Tool 7: 캐시 초기화 (인자 없음) ───────────────────────────────────

class ClearCacheRequest(_ToolModel):
    """캐시 전체 초기화 (인자 없음)."""


# ── Tool 8: OLTA 검색 ────────────────────────────────────────────────

class SearchOltaRequest(_ToolModel):
    question: str = Field(..., min_length=1, max_length=2000)
    custom_queries: list[str] | None = None
    categories: list[str] | None = None
    priority_boards: list[str] | None = None
    max_results: int = Field(10, ge=1, le=100)
    skip_bbs: bool = False


# ── Tool 9: 지방세 질의응답 (전체 파이프라인) ────────────────────────

class AskLocalTaxRequest(_ToolModel):
    question: str = Field(..., min_length=1, max_length=2000)
    custom_queries: list[str] | None = None
    categories: list[str] | None = None
    priority_boards: list[str] | None = None
    skip_verification: bool = True


# ── 제네릭 응답 래퍼 (PR#2 이후 선택 사용) ──────────────────────────

class ToolResult(BaseModel, Generic[T]):
    """PR#2 이후 tools/* 가 markdown 외 구조화 응답을 병행할 때 쓸 래퍼.

    현재는 모든 tool 이 `str` 을 반환하므로 사용되지 않으나, 계약 확장 지점으로
    남겨 둔다. `ok=False` 시 `error_message` 필드를 채운다.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    markdown: str
    data: T | None = None
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


TOOL_REQUEST_MODELS: dict[str, type[_ToolModel]] = {
    "check_olta_login": CheckOltaLoginRequest,
    "open_olta_for_login": OpenOltaForLoginRequest,
    "close_olta_browser": CloseOltaBrowserRequest,
    "get_search_plan": GetSearchPlanRequest,
    "show_answer_in_browser": ShowAnswerInBrowserRequest,
    "get_document_content": GetDocumentContentRequest,
    "clear_cache": ClearCacheRequest,
    "search_olta": SearchOltaRequest,
    "ask_local_tax": AskLocalTaxRequest,
}


__all__ = [
    "CheckOltaLoginRequest",
    "OpenOltaForLoginRequest",
    "CloseOltaBrowserRequest",
    "GetSearchPlanRequest",
    "ShowAnswerInBrowserRequest",
    "GetDocumentContentRequest",
    "ClearCacheRequest",
    "SearchOltaRequest",
    "AskLocalTaxRequest",
    "ToolResult",
    "TOOL_REQUEST_MODELS",
]
