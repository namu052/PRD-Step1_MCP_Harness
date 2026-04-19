# backend-step5-crawler-concurrent-cache-refactor — 크롤러 병렬화·영속 캐시·구조 리팩터 (L)

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, design-docs/01-crawler-concurrency-and-cache, active/backend-step4-pipeline-instrumentation-baseline

## 1. Why (배경·문제)
`_search_all_bbs_boards`(crawler_service.py:2017~)는 query·page 모두 중첩 직렬이라 crawl 단계가 전체 응답의 **최대 병목**(P50 ~120s). in-memory TTL 5분 캐시는 재시작 시 소실되고, 3,537줄 단일 파일(TD-0002)은 변경 자체가 고위험이다. 이 plan이 먼저 들어가야 Step6/7/8의 "전체 응답 P50 90s" 예산이 성립한다.

## 2. Scope
### In
- query 병렬화: `asyncio.gather(*(...for q in queries))` + `BBS_CONCURRENCY` 세마포어(기본 4)
- 페이지네이션 파이프라이닝: 다음 페이지 `goto` lookahead 1
- 컬렉션 수집 병렬화 (N=2)
- SQLite 영속 캐시 `backend/data/crawl_cache.db` (WAL, TTL 1h, schema_version 컬럼)
- `TimeBudget` 클래스 — 예산 전파, 초과 시 partial result
- crawler_service 리팩터 → `backend/app/services/crawlers/{browser_session,bbs/{search,detail,merge},collection/search,selectors,urls,cache}.py`
- 퍼사드 `crawler_service.py` ≤150줄, 기존 import 경로 100% re-export
- `_merge_bbs_board_records`(446~504) 3함수 분해 + 한글 자모 정규화
### Out
- OLTA 사이트 쪽 변경
- BBS 응답 스키마 변경
- 신규 게시판 추가

## 3. Definition of Done
- [ ] **baseline 대비 crawl 단계 P50 -60% 이상** (Step4 리포트 diff를 PR 첨부)
- [ ] SQLite 캐시 히트 시 crawl P50 ≤ 3s (측정치 첨부)
- [ ] `structure-check.py --strict` 위반 0건 (TD-0002, TD-0003 resolved)
- [ ] `tests/crawlers/test_concurrency.py` (query 병렬성, TimeBudget early-return, 세마포어 상한 3건)
- [ ] `tests/crawlers/test_bbs_merge.py` (라벨 공백/줄바꿈/자모/중복/역순 5건)
- [ ] 기존 `test_bbs_crawler.py` 회귀 0건
- [ ] 골든셋 baseline 대비 `verified_citation_rate` 회귀 없음 (품질 가드)
- [ ] 내부 PR 5개 분할: A) facade+browser_session B) selectors/urls C) bbs/ D) collection/ E) cache+TimeBudget. 각 ≤400 LOC
- [ ] `tech-debt-tracker.md` TD-0002, TD-0003 → `resolved` (Ref에 각 PR 링크/해시)

## 4. 구현 단계
1. PR-A: `browser_session.py` 추출 (140~411), crawler_service.py가 re-export하도록 퍼사드화. 회귀 테스트만 수정
2. PR-B: `selectors.py` + `urls.py` (순수 함수 2527~2810 이전). 저위험
3. PR-C: `crawlers/bbs/*` — `search.py`에 query 병렬화 + 페이지 lookahead. `merge.py`에 `_merge_bbs_board_records` 3분할 + 한글 자모 정규화. 테스트 추가.
4. PR-D: `crawlers/collection/search.py` — N=2 병렬. 타임아웃·재시도 `retry_with_backoff` 도입
5. PR-E: `crawlers/cache.py` — SQLite adapter, `TimeBudget` 클래스. `_MCPSession.get_crawl`이 cache miss 시 SQLite 조회
6. 최종: 퍼사드 슬림화, `structure-check --strict` 통과 확인, baseline 리포트 재측정 및 diff

## 5. 위험 & 롤백
- 위험1: OLTA rate-limit/세션 레이스 → `BBS_CONCURRENCY=4` 기본, 운영 중 `BBS_CONCURRENCY=1`로 즉시 직렬 회귀 가능. 4xx/429 감지 시 자동 backoff
- 위험2: 외부 import가 private 함수 참조 → PR-A 전에 `grep -R "from app.services.crawler_service" backend/` 스냅샷 저장, 퍼사드 `__all__`로 표면 고정
- 위험3: 캐시 stale → schema_version으로 무효화 + 응답 헤더 `x-crawl-cache-age` 로깅. 운영 중 의심 시 파일 삭제로 cold start
- 롤백: 각 PR 단위 revert. 퍼사드가 동일 심볼을 export하므로 부분 롤백 안전

## 6. 검증 계획
- 단위: `tests/crawlers/test_concurrency.py`, `test_bbs_merge.py`
- 통합: `scripts/verify.sh --full`
- 수동: `backend/tests/scratch/test_bbs_live.py` 1회 실행하여 회귀 감지
- 성능: `scripts/bench-pipeline.sh --n 5 --report` 후 Step4 baseline과 diff 첨부

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 선행: Step4 baseline 완료 필수. TD-0002/0003 scheduled.
- 2026-04-18 — PR#1 (인프라) 착수·완료:
  - `backend/app/services/crawlers/time_budget.py` (TimeBudget + TimeBudgetExpired)
  - `backend/app/services/crawlers/crawl_cache.py` (SQLite KV, SHA256 key, TTL/스키마 버전 기반 무효화)
  - `backend/app/services/crawlers/__init__.py` (공개 API)
  - `backend/app/feature_flags.py` (BBS_CONCURRENCY / CRAWL_CACHE_TTL_SEC / CRAWL_TIME_BUDGET_SEC 등 집중 관리)
  - `backend/tests/test_crawler_infra.py` 9건 green (TimeBudget decay/expire/sub + cache roundtrip/ttl/disabled/purge + key stability)
  - `_merge_bbs_board_records` 60줄 → `_collect_bbs_candidates / _merge_with_fallbacks / _append_remaining` 3함수(각 ≤50). **TD-0003 resolved**.
  - **잔여(PR#2~5 이월)**: `_search_all_bbs_boards` asyncio.gather + BBS_CONCURRENCY 세마포어 실제 적용, Playwright 페이지 풀, collection_service 병렬, crawler_service 3,537줄 facade 분할. 이들 작업은 live OLTA 통합 테스트가 필수이므로 GPKI 세션에서 수행.
  - **TD-0002 상태**: `resolved` 아님 → `in-progress` (인프라만 들어감). facade 분할 완료 시 resolved 전환.
