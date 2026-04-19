# 02 — Hybrid Retrieval and Domain Priors

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead
**Related**: product-specs/overview, exec-plans/active/backend-step6-retrieval-hybrid-rerank, design-docs/03-verification-tiers-and-multiround

## Problem
현재 `embedding_service.py`는 **순수 임베딩 코사인 유사도**로만 랭킹한다(`grep BM25|rerank|hybrid` → No matches). 지방세 도메인 질의는 "취득세 감면 대상" 같은 **정확 용어 매칭이 핵심**인 경우가 많아 임베딩 단독으로는 법령 원문을 판례/커뮤니티보다 아래 랭킹할 위험이 있다. 또한 `ThreadPoolExecutor(max_workers=1)`로 임베딩 계산이 직렬화되어 있어 랭킹 P50이 ~5s 수준.

## Options
### Option A — 순수 임베딩 유지, 배치화만
pros: 변화 최소
cons: 정확 용어 매칭 약점 유지, 품질 개선 없음

### Option B — BM25 + 임베딩 선형 결합 + 도메인 priors
pros: 업계 표준(Reciprocal Rank Fusion/weighted sum), 구현 단순, CPU-only
cons: alpha 튜닝 필요

### Option C — Cross-encoder rerank (cohere/bge-reranker 등)
pros: 품질 상한 가장 높음
cons: 외부 모델 의존 + 비용, 레이턴시 증가 가능, 이번 스프린트 범위 초과

## Decision
**Option B**. 단계적 확장 경로는 C로 열어둠.

### 하이브리드 점수식
```
score(doc) = alpha * embed_cos(q, doc)
           + (1 - alpha) * bm25_norm(q, doc)
score(doc) *= domain_prior[doc.source_type]
```

- `alpha` 기본 **0.6** (임베딩 우위). 골든셋으로 A/B (0.4 / 0.6 / 0.8)
- `bm25_norm`: `rank_bm25.BM25Okapi` 점수를 min-max 정규화 (배치 호출마다)
- `domain_prior`: YAML 외부화, 초기값

```yaml
# backend/app/config/domain_priors.yaml
official_law:       1.30   # 법령/시행령/시행규칙
official_case:      1.20   # 판례, 심판례
official_interpret: 1.15   # 유권해석, 예규
official_qna:       1.05   # OLTA BBS 공식 Q&A
community:          0.90
web_other:          0.80
unknown:            1.00
```

### 임베딩 배치화
- `ThreadPoolExecutor(max_workers=1)` 제거
- OpenAI embeddings API는 `input: list[str]`를 배치 수용 → 한 번에 최대 32개 텍스트
- 실패 시 half-split 재시도 (128 → 64 → 32)

### SearchPlan 캐시
- 키: `sha256(normalize(question))`
- LRU 메모리 캐시(크기 256) + SQLite 백업(TTL 24h)
- `question_type` 분기 프롬프트: 감면 / 부과 / 신고 / 일반 (프롬프트 파일은 `backend/app/prompts/search_plan_<type>.py`)

## Consequences
- **+** 정확 용어 매칭 품질 상승 (예상 `verified_citation_rate` +15%p)
- **+** 랭킹 P50 5s → 2s (배치화 + 캐시 히트)
- **+** 프런트 `ConfidenceBadge`/`SourceCard`가 `source_type` prior를 볼 수 있게 되면서 UX 설명력 향상
- **−** alpha/priors 가 운영 중 조정 포인트로 추가됨 — YAML 편집 + reload로 충분
- **−** 초기에는 `rank_bm25` 의존성 추가 (순수 Python)

## Follow-ups
- `exec-plans/active/backend-step6-retrieval-hybrid-rerank.md`
- 3개월 후 cross-encoder(bge-reranker-base 등) 도입 평가 → 별도 design-doc
- `source_type` enum 스키마가 프런트와 싱크되어야 함 (design-doc 03에서 확정)
