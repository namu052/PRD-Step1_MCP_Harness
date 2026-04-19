"""bm25.py — 순수 파이썬 BM25 스코어러.

외부 의존 (`rank_bm25`) 를 피하기 위해 Okapi BM25 를 직접 구현.
k1=1.5, b=0.75 (표준값). 토큰화는 공백 + 한글 이어쓰기 추출 정도로 단순.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z가-힣0-9]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class BM25Scorer:
    """문서 묶음을 인덱스화하고, 쿼리별 점수를 제공."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = corpus_tokens
        self.doc_count = len(corpus_tokens)
        self.doc_lengths = [len(doc) for doc in corpus_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / self.doc_count if self.doc_count else 0.0
        )
        self.df: Counter[str] = Counter()
        for doc in corpus_tokens:
            for term in set(doc):
                self.df[term] += 1

    def score(self, query_tokens: Iterable[str], doc_index: int) -> float:
        if not self.avg_doc_length:
            return 0.0
        doc = self.corpus_tokens[doc_index]
        if not doc:
            return 0.0
        tf = Counter(doc)
        dl = self.doc_lengths[doc_index]
        norm = 1.0 - self.b + self.b * (dl / self.avg_doc_length)
        total = 0.0
        for term in set(query_tokens):
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1.0 + (self.doc_count - df + 0.5) / (df + 0.5))
            term_freq = tf.get(term, 0)
            if term_freq == 0:
                continue
            total += idf * (term_freq * (self.k1 + 1.0)) / (term_freq + self.k1 * norm)
        return total

    def scores_for_query(self, query: str) -> list[float]:
        q_tokens = tokenize(query)
        return [self.score(q_tokens, i) for i in range(self.doc_count)]

    @staticmethod
    def normalize(scores: list[float]) -> list[float]:
        """[0, 1] 로 정규화 — 하이브리드 결합 시 embedding(코사인)과 스케일 맞춤."""
        if not scores:
            return []
        hi = max(scores)
        if hi <= 0.0:
            return [0.0] * len(scores)
        return [s / hi for s in scores]
