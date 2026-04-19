# 01 — Crawler Concurrency and Persistent Cache

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead
**Related**: product-specs/overview, exec-plans/active/backend-step5-crawler-concurrent-cache-refactor

## Problem
`backend/app/services/crawler_service.py`의 `_search_all_bbs_boards`(2017~)는 `for query in queries:`와 `for page_index in range(max_pages):`가 **중첩 직렬**이라 crawl 단계가 P50 ~120s, P95 ~360s 로 전체 응답의 최대 병목이다. 또한 `_MCPSession`의 in-memory TTL 캐시는 프로세스 재시작이나 워커 분리 시 증발해 반복 질의에도 매번 크롤링을 재실행한다. crawler_service.py 자체가 3,537줄로 구조 위반(TD-0002)이라 변경 자체가 고위험.

## Options
### Option A — query·page 양쪽 모두 병렬 + 페이지 풀
pros: 이론상 최대 승리 (N×M 병렬), Playwright 컨텍스트 재사용 가능
cons: OLTA rate-limit/세션 레이스, 실패 격리 복잡

### Option B — query만 병렬(N=4), 페이지는 파이프라이닝(1 lookahead)
pros: 구현 단순, 레이스 리스크 낮음, 대부분의 이득 확보(예상 -55~65%)
cons: Option A 대비 일부 상한

### Option C — 영속 캐시만 도입, 병렬화 보류
pros: 구조 변경 없음
cons: 첫 호출 지연 그대로

## Decision
**Option B 채택 + 영속 캐시 병행**. 세마포어 `BBS_CONCURRENCY=4`(env로 조정), 페이지네이션은 `asyncio.create_task`로 다음 페이지 `goto`를 미리 발사하고 현재 페이지 파싱과 겹침. SQLite 영속 캐시(`backend/data/crawl_cache.db`, WAL 모드, TTL 1h) 동시 도입. 구조 리팩터(퍼사드 + `crawlers/` 서브모듈)는 **병렬화 로직이 최종 모듈에 한 번만 들어가도록** 같은 plan에서 처리.

### 캐시 키 & 스키마
```
key = sha256(question_norm || "|" || sorted(priority_boards) || "|" || sorted(search_queries))
columns: (key TEXT PK, created_at INTEGER, expires_at INTEGER, payload BLOB, schema_version INTEGER)
```
`schema_version`이 다르면 miss 처리 (스키마 진화 안전).

### TimeBudget 전파
```python
budget = TimeBudget(total=180)  # 최상위에서 설정
async with budget.subspan("crawl", max=120) as sub:
    results = await crawler.search_all(queries, budget=sub)
    # sub 초과 시 sub.exceeded → partial result 반환
```

### 리팩터 계층
```
crawler_service.py (퍼사드, ≤150줄, 기존 import 경로 re-export)
  └── crawlers/
      ├── browser_session.py   # 140~411 이전
      ├── selectors.py         # 2527~2810 이전 (순수 함수)
      ├── urls.py              # URL 빌더
      ├── bbs/
      │   ├── search.py        # _search_all_bbs_boards 병렬 버전
      │   ├── detail.py        # _fetch_detail
      │   └── merge.py         # _merge_bbs_board_records 3분할
      ├── collection/
      │   └── search.py        # 컬렉션 수집
      └── cache.py             # SQLite adapter
```

## Consequences
- **+** crawl 단계 P50 -60% 예상(측정 DoD로 강제)
- **+** 캐시 히트 시 crawl P50 ≤ 3s
- **+** TD-0002, TD-0003 자연 해소
- **−** Playwright 메모리 사용량 증가 (페이지 풀 N=4 → 약 4x). 기본 워커는 N=4 유지하되 환경변수로 축소 가능
- **−** SQLite 파일 관리 필요 (backup/vacuum 정책은 `.gitignore` 처리 + 크기 상한 500MB)
- neutral: Playwright `BrowserContext`당 실제 병렬 허용도는 사이트 의존 → 실측 후 기본값 재조정 여지

## Follow-ups
- `exec-plans/active/backend-step5-crawler-concurrent-cache-refactor.md`
- 캐시 히트율이 30% 이하로 관찰되면 키 설계 재검토 (design-doc 01a 보충)
- OLTA rate-limit 경고 로그 발생 시 N=2로 즉시 축소하는 자동 adaptive policy 후속 문서로 검토
