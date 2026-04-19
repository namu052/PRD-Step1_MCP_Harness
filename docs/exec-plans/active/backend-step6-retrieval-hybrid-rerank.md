# backend-step6-retrieval-hybrid-rerank — BM25+임베딩 하이브리드, 도메인 priors, 배치화, SearchPlan 캐시

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, design-docs/02-hybrid-retrieval-and-domain-priors, active/backend-step4-pipeline-instrumentation-baseline

## 1. Why (배경·문제)
현재 랭킹은 순수 임베딩 코사인만 사용(grep `BM25|rerank|hybrid` → No matches). 지방세 질의는 "취득세 감면 대상" 같은 **정확 용어 매칭**이 핵심인 경우가 많아 법령 원문이 커뮤니티보다 밀려 랭킹될 수 있다. 또한 `embedding_service.py`가 `ThreadPoolExecutor(max_workers=1)` 직렬이라 랭킹 P50 ~5s.

## 2. Scope
### In
- `rank_bm25` 라이브러리 도입
- 하이브리드 점수: `alpha * embed_cos + (1-alpha) * bm25_norm`, `alpha=0.6` 기본
- `domain_priors` YAML (`backend/app/config/domain_priors.yaml`)로 소스 타입별 가중치
- 임베딩 배치화: OpenAI embeddings API 배치 호출(N=32, 실패 시 half-split 재시도), ThreadPool 제거
- `SearchPlan` 캐시: 메모리 LRU(256) + SQLite 백업(TTL 24h). 키 = `sha256(normalize(question))`
- 질문 타입 분기 프롬프트: `prompts/search_plan_{gamyeon,bugwa,shingo,ilban}.py`
- feature flag `RETRIEVAL_MODE=embedding|hybrid` (기본 `hybrid`)
### Out
- 재학습 임베딩 모델
- 별도 벡터 DB 도입
- Cross-encoder 재순위화(design-doc 02 Follow-up)

## 3. Definition of Done
- [ ] golden set `verified_citation_rate` **baseline +15%p 이상** (Brier score 비악화)
- [ ] 랭킹 단계 P50 baseline 대비 **-50% 이상** (Step4 리포트 diff 첨부)
- [ ] `alpha` A/B 리포트 (0.4/0.6/0.8) `observability/reports/<date>-bm25-ab.md` 커밋
- [ ] SearchPlan 캐시 히트율 ≥ 30% (골든셋 재호출 기준)
- [ ] 도메인 priors YAML 핫리로드 동작 테스트
- [ ] `scripts/verify.sh --full` 통과
- [ ] 신규 `tests/retrieval/test_hybrid_rank.py`, `test_embedding_batch.py`, `test_search_plan_cache.py`
- [ ] PR ≤400 LOC (A/B 리포트 md는 LOC 외)

## 4. 구현 단계
1. `requirements.txt`에 `rank_bm25` 추가, `embedding_service.py` 배치화 리팩터 + ThreadPool 제거
2. `backend/app/services/retrieval/bm25.py` 추가, `embedding_service.rank_results`가 hybrid 점수를 합산하도록 주입
3. `domain_priors.yaml` + 로더 (`backend/app/config/priors.py`), reload 지원
4. `SearchPlanCache` 클래스 (in-memory LRU + `SessionStore.sqlite_store` 공유, namespace=`search_plan`)
5. `prompts/search_plan_*.py` 4종 + `search_service.build_search_plan` 분기
6. feature flag `RETRIEVAL_MODE` 도입 (`backend/app/feature_flags.py`)
7. `scripts/bench-pipeline.sh --alpha 0.4 --alpha 0.6 --alpha 0.8` 실행하여 A/B 리포트 생성

## 5. 위험 & 롤백
- 위험1: alpha 잘못 튜닝 → 회귀 발생. `RETRIEVAL_MODE=embedding`로 즉시 복귀 가능. 기본값은 A/B 결과로 결정 후 YAML 기록
- 위험2: domain_priors 잘못 설정 → 모든 소스에 1.0 fallback 값 지원, YAML 파싱 실패 시 기본 1.0
- 위험3: 배치 임베딩 호출 실패 → half-split 재시도(128→64→32→16→8→1), 최종 실패 시 fallback 키워드 랭킹
- 롤백: `RETRIEVAL_MODE=embedding` + `SEARCH_PLAN_CACHE=off` 환경변수로 전량 off

## 6. 검증 계획
- 단위: BM25 정규화, 배치 half-split, 캐시 LRU 동작, priors 핫리로드 — 각 테스트
- 통합: `scripts/verify.sh --full`
- 품질: 골든셋 수동 비교 (≥3 질문은 정답 소스가 상위 3 안에 있어야)
- 성능: `scripts/bench-pipeline.sh --n 5 --report` diff

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 선행: Step4 baseline. Step5와 파일 독립이라 병렬 진행 가능.
- 2026-04-18 — PR#1 (핵심) 착수·완료:
  - `backend/app/services/retrieval/{bm25,domain_priors,hybrid_scorer}.py` + `__init__.py` (순수 파이썬 BM25, k1=1.5/b=0.75)
  - `backend/config/domain_priors.yml` (official_law 1.20 … web 0.85)
  - `backend/app/services/embedding_service.py` 에 `RETRIEVAL_MODE=hybrid` 분기 (기본), `embedding` 모드 fallback 유지
  - `backend/requirements.txt` 에 `PyYAML==6.0.2` 추가
  - `backend/tests/test_retrieval_hybrid.py` 8건 green (tokenize / bm25 score / normalize / priors / alpha=0·1·중간)
  - 기존 `_rank_results_sync` 회귀 0건 (81 passed)
  - **잔여(PR#2~)**: 임베딩 배치화(max_workers=1 → 배치 N=32), SearchPlan LRU+SQLite 캐시, 질문 타입 분기 프롬프트, BM25 α A/B 실험 리포트는 live 환경 필요 — 인증 세션으로 이월.
