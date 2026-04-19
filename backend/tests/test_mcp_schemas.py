"""Plan 4 PR#1 — 9개 Tool 입력 pydantic 모델 단위 검증."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.mcp.schemas import (
    AskLocalTaxRequest,
    CheckOltaLoginRequest,
    ClearCacheRequest,
    CloseOltaBrowserRequest,
    GetDocumentContentRequest,
    GetSearchPlanRequest,
    OpenOltaForLoginRequest,
    SearchOltaRequest,
    ShowAnswerInBrowserRequest,
    TOOL_REQUEST_MODELS,
    ToolResult,
)


def test_tool_request_models_registry_has_all_nine():
    expected = {
        "check_olta_login",
        "open_olta_for_login",
        "close_olta_browser",
        "get_search_plan",
        "show_answer_in_browser",
        "get_document_content",
        "clear_cache",
        "search_olta",
        "ask_local_tax",
    }
    assert set(TOOL_REQUEST_MODELS) == expected


def test_zero_arg_tools_accept_empty_dict():
    for cls in (
        CheckOltaLoginRequest,
        OpenOltaForLoginRequest,
        CloseOltaBrowserRequest,
        ClearCacheRequest,
    ):
        cls.model_validate({})


def test_zero_arg_tools_reject_extra_fields():
    with pytest.raises(ValidationError):
        CheckOltaLoginRequest.model_validate({"garbage": 1})


def test_get_search_plan_requires_non_empty_question():
    GetSearchPlanRequest.model_validate({"question": "취득세 감면"})
    with pytest.raises(ValidationError):
        GetSearchPlanRequest.model_validate({"question": ""})
    with pytest.raises(ValidationError):
        GetSearchPlanRequest.model_validate({})


def test_show_answer_requires_html():
    ShowAnswerInBrowserRequest.model_validate({"html_content": "<h1>x</h1>"})
    with pytest.raises(ValidationError):
        ShowAnswerInBrowserRequest.model_validate({"html_content": ""})


def test_get_document_content_requires_source_id():
    GetDocumentContentRequest.model_validate({"source_id": "test_law_001"})
    with pytest.raises(ValidationError):
        GetDocumentContentRequest.model_validate({"source_id": ""})


def test_search_olta_defaults_and_overrides():
    req = SearchOltaRequest.model_validate({"question": "취득세"})
    assert req.max_results == 10
    assert req.skip_bbs is False
    assert req.custom_queries is None

    req2 = SearchOltaRequest.model_validate(
        {
            "question": "취득세 감면",
            "custom_queries": ["서민주택 취득세", "감면 요건"],
            "categories": ["law_search"],
            "priority_boards": ["질의응답"],
            "max_results": 20,
            "skip_bbs": True,
        }
    )
    assert req2.max_results == 20
    assert req2.skip_bbs is True
    assert req2.categories == ["law_search"]


def test_search_olta_rejects_out_of_range_max_results():
    with pytest.raises(ValidationError):
        SearchOltaRequest.model_validate({"question": "q", "max_results": 0})
    with pytest.raises(ValidationError):
        SearchOltaRequest.model_validate({"question": "q", "max_results": 200})


def test_ask_local_tax_defaults():
    req = AskLocalTaxRequest.model_validate({"question": "취득세 감면 대상"})
    # 현재 mcp_server.py:615 와 동일한 기본값
    assert req.skip_verification is True
    assert req.custom_queries is None


def test_tool_result_wrapper_roundtrip():
    r = ToolResult[dict](markdown="## ok", data={"x": 1})
    assert r.ok is True
    d = r.model_dump()
    assert d["markdown"] == "## ok"
    assert d["data"] == {"x": 1}
    assert d["error_message"] is None


def test_frozen_models_are_hashable_and_immutable():
    r = GetSearchPlanRequest.model_validate({"question": "q1"})
    with pytest.raises(ValidationError):
        # frozen → 변경 불가
        r.question = "q2"  # type: ignore[misc]
