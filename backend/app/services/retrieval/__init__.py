"""retrieval/ — Plan 2 하이브리드 랭킹 모듈.

feature_flags.retrieval_mode="hybrid" 일 때 embedding_service 가 여기의
hybrid_scorer + domain priors 를 사용한다. "embedding" 모드로 즉시 회귀 가능.
"""
from .bm25 import BM25Scorer
from .domain_priors import load_domain_priors
from .hybrid_scorer import hybrid_score

__all__ = ["BM25Scorer", "load_domain_priors", "hybrid_score"]
