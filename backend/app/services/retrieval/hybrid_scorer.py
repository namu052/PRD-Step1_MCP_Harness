"""hybrid_scorer.py — 임베딩 코사인 + BM25 + 도메인 priors 결합.

final = prior * ( α * cosine + (1 - α) * bm25_norm )

α (alpha) = feature_flags.retrieval_alpha (default 0.6).
prior 는 source_type 별 곱셈 가중치(1.2~0.85 범위).
"""
from __future__ import annotations

from typing import Iterable

from app.models.schemas import CrawlResult

from .bm25 import BM25Scorer, tokenize
from .domain_priors import prior_for


def build_corpus_tokens(results: Iterable[CrawlResult], content_limit: int = 1500) -> list[list[str]]:
    docs: list[list[str]] = []
    for r in results:
        blob = f"{r.title} {r.preview} {r.content[:content_limit]}"
        docs.append(tokenize(blob))
    return docs


def hybrid_score(
    question: str,
    results: list[CrawlResult],
    cosines: list[float],
    alpha: float,
    content_limit: int = 1500,
) -> list[float]:
    """동일 길이 3-벡터(results, cosines)에 대해 하이브리드 점수를 반환.

    cosines: 이미 계산된 코사인 유사도(0~1 범위 가정). 없으면 0.
    alpha: [0, 1] — 1이면 embedding-only, 0이면 BM25-only.
    """
    if not results:
        return []
    alpha = max(0.0, min(1.0, alpha))
    corpus = build_corpus_tokens(results, content_limit)
    bm25 = BM25Scorer(corpus)
    bm25_raw = bm25.scores_for_query(question)
    bm25_norm = BM25Scorer.normalize(bm25_raw)
    out: list[float] = []
    for idx, r in enumerate(results):
        cos = cosines[idx] if idx < len(cosines) else 0.0
        blended = alpha * cos + (1.0 - alpha) * bm25_norm[idx]
        out.append(blended * prior_for(r.type))
    return out
