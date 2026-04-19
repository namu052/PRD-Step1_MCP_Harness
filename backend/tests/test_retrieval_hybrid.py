"""Plan 2 — BM25 + 도메인 priors + hybrid 결합 검증."""
from __future__ import annotations

import os

import pytest

from app import feature_flags as ff
from app.models.schemas import CrawlResult
from app.services.retrieval import BM25Scorer, hybrid_score
from app.services.retrieval.bm25 import tokenize
from app.services.retrieval.domain_priors import prior_for, _reset_cache_for_tests


@pytest.fixture(autouse=True)
def _restore_env():
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)
    ff._reload_for_tests()
    _reset_cache_for_tests()


def _mk(id_: str, title: str, content: str, type_: str = "unknown") -> CrawlResult:
    return CrawlResult(
        id=id_, title=title, type=type_, content=content,
        preview=content[:80], url=f"https://ex/{id_}",
    )


def test_tokenize_korean_and_english():
    tokens = tokenize("취득세 감면 article 제99조 2024년")
    # 한글/영문/숫자 모두 추출
    assert "취득세" in tokens
    assert "감면" in tokens
    assert "article" in tokens
    assert "제99조" in tokens
    assert "2024년" in tokens


def test_bm25_query_matches_relevant_doc_higher():
    docs = [
        tokenize("취득세 감면 기준 주택"),
        tokenize("전혀 무관한 요리 레시피"),
        tokenize("감면 주택 매매 정보"),
    ]
    scorer = BM25Scorer(docs)
    scores = scorer.scores_for_query("취득세 감면 주택")
    assert scores[0] > scores[1]
    assert scores[2] > scores[1]


def test_bm25_normalize_to_unit_range():
    scores = [0.0, 2.0, 4.0]
    norm = BM25Scorer.normalize(scores)
    assert norm[-1] == 1.0
    assert all(0.0 <= s <= 1.0 for s in norm)


def test_domain_priors_official_outranks_web():
    assert prior_for("official_law") > prior_for("web")
    assert prior_for("official_case") > prior_for("community")
    # 미지/None 은 1.0
    assert prior_for("unknown") == 1.0
    assert prior_for(None) == 1.0


def test_hybrid_score_prefers_official_source_equal_relevance():
    # 동일한 내용, 다른 타입 — prior 로 official 이 더 높아야
    results = [
        _mk("a", "취득세 감면", "취득세 감면 내용", type_="web"),
        _mk("b", "취득세 감면", "취득세 감면 내용", type_="official_law"),
    ]
    cosines = [0.8, 0.8]
    scores = hybrid_score("취득세 감면", results, cosines, alpha=0.6)
    assert scores[1] > scores[0]


def test_hybrid_alpha_0_collapses_to_bm25():
    results = [
        _mk("a", "취득세 감면", "취득세 감면 계산 예시", type_="official_law"),
        _mk("b", "자동차세 납부", "자동차세 납부 안내", type_="official_law"),
    ]
    cosines = [0.0, 0.99]  # 임베딩은 반대로 왜곡
    scores_bm25_only = hybrid_score("취득세 감면", results, cosines, alpha=0.0)
    # α=0 이면 BM25만 본다 → 취득세 감면 쿼리는 a 문서가 더 높아야 함
    assert scores_bm25_only[0] > scores_bm25_only[1]


def test_hybrid_alpha_1_collapses_to_embedding():
    results = [
        _mk("a", "다른 주제", "다른 주제 본문", type_="unknown"),
        _mk("b", "또 다른 주제", "또 다른 주제 본문", type_="unknown"),
    ]
    cosines = [0.2, 0.9]
    scores = hybrid_score("aa", results, cosines, alpha=1.0)
    assert scores[1] > scores[0]


def test_hybrid_empty_results_returns_empty():
    assert hybrid_score("q", [], [], alpha=0.6) == []
