# 백엔드 제품 고도화 — 전체 설명 & 워크플로우

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Scope**: backend (frontend는 계약 합의만)
**Related**: exec-plans/active/backend-step4~step9, design-docs/00~05

> Claude Code plan mode에서 승인된 meta-plan(`.claude/plans/starry-coalescing-patterson.md`)을
> 저장소 내 참조 가능한 형태로 옮긴 요약본. 세부 DoD·단계는 각 active plan을 본다.

---

## 1. 고도화 방향 — 이중축 (Dual-axis)

| 축 | 목표 | 현재 추정 | 목표치 |
|----|------|-----------|--------|
| **L (Latency↓)** | 체감 TTFT 대폭 단축 | TTFT P50 ~15s, 전체 P50 ~180s | TTFT P50 **≤3s**, 전체 P50 **≤90s** |
| **Q (Quality↑)** | 근거 기반 신뢰도 강화 | 3-tier, 단방향 hallucination check | 5-tier Brier ≤0.10, `verified_citation_rate ≥0.85`, `hallucination_rate ≤0.05` |

핵심 원칙: **구조 리팩터(TD-0001/0002/0003/0004)는 품질·레이턴시 개선의 인에이블러로만 수용**. 리팩터 자체가 목적이 아님.

---

## 2. 현 상태의 레버 (Phase 1 실측 확인)

| 축 | 병목 | 근거 (code grep) |
|----|------|------------------|
| **L** | BBS 통합 검색 query·page **직렬** | `crawler_service.py:2044 for query in queries:`, `:2075 for page_index in range(max_pages)` |
| **L** | 임베딩 랭킹 `ThreadPoolExecutor(max_workers=1)` | `embedding_service.py:36` |
| **L** | 캐시 in-memory dict + 프로세스 재시작 시 소실 | `mcp_server.py _MCPSession` (57~115) |
| **L** | TTFT: Stage 1~5 완료 이후에만 스트리밍 시작 | `_run_full_pipeline` 657~887 직렬 체인 |
| **L** | revision 루프가 서킷 브레이커 없이 60s 추가 | `mcp_server.py:955-973` (verifier 자체는 이미 gather 병렬) |
| **Q** | BM25 / 도메인-우선 rerank **부재** | grep `BM25\|rerank\|hybrid` → No matches |
| **Q** | 신뢰도 tier 3단계, 칼리브레이션 없음 | `verification_aggregator.py` + `ConfidenceBadge` |
| **Q** | KEYWORD_PATTERN / CONTRADICTION_PAIRS 하드코딩 | `content_verifier.py:13,42` |
| **Q** | 환각 탐지 단방향(claim→evidence), 역방향 부재 | `grouped_answer_verifier.py` |
| **Q** | revision 단일 라운드, early stopping 없음 | `_run_verification` 955 |

---

## 3. 6-Plan 분해 (4 필수 + 2 옵션)

```
(기존 active: step2 E2E, step3 검증 E2E — 회귀 안전망)
        │
        ▼
 [Plan 0] step4 instrumentation baseline  (S, 필수 선행)
        │
        ├─► [Plan 1] step5 crawler 병렬+캐시+리팩터  (L)  ─┐
        │                                                     │
        ├─► [Plan 2] step6 하이브리드 검색+rerank     (M)  ─┤─► [Plan 4] step8 mcp 분할 + progressive SSE (M-L)
        │                                                     │
        └─► [Plan 3] step7 검증 multi-round+tiers     (M-L)─┘
 [Plan 5] step9 scratch 정리 (S, 옵션) — Plan 1과 병렬
```

| # | slug | 축 | 규모 | TD 해소 | 예상 효과 |
|---|------|-----|------|---------|-----------|
| 0 | step4 baseline | 측정 | S | - | 회귀 가드 전제 |
| 1 | step5 crawler | **L↓(최대)** + 구조 | L | 0002, 0003 | crawl P50 -60%, 캐시 히트시 ≤3s |
| 2 | step6 retrieval | **Q↑** + 보조 L↓ | M | - | `verified_citation_rate` +15%p, rank P50 -50% |
| 3 | step7 verification | **Q↑** + L↓(early stop) | M-L | 0004 | `hallucination_rate ≤0.05`, Brier ≤0.10 |
| 4 | step8 mcp + SSE | **L↓(체감 TTFT)** + 구조 | M-L | 0001 | 체감 TTFT ≤3s |
| 5 | step9 scratch | 위생 | S | 0008, 0009 | - |

---

## 4. 실행 워크플로우 (4 Phase)

### Phase A — 측정 (Plan 0, 2~3일)
계측 없는 최적화는 회귀 방지 불가. 코드 행동 변경 없음.
- `@stage_timed` 데코레이터 → `observability/metrics/pipeline.jsonl`
- 골든셋 20문항 (`tests/quality/golden_questions.yaml`) — 감면 10 / 부과 5 / 신고 3 / 매칭없음 2
- `scripts/bench-pipeline.sh --n 3 --report` → P50/P95 baseline 리포트 커밋
- **Gate**: 이후 모든 plan PR은 이 baseline 대비 diff 첨부 필수

### Phase B — 병렬 개선 (Plan 1, 2, 3 동시 진행 가능)
파일 독립 → 세 plan을 병렬 브랜치로 돌린다.
- **Plan 1 (crawler)**: query 병렬 `asyncio.gather` (N=4), page pipelining, SQLite 영속 캐시 TTL 1h, TimeBudget 클래스 도입. 내부 PR 5개 분할.
- **Plan 2 (retrieval)**: `rank_bm25` + embedding 하이브리드(α=0.6 기본), 도메인 priors YAML, 임베딩 배치화 N=32, SearchPlan LRU+SQLite 캐시.
- **Plan 3 (verification)**: `aggregate` 4함수 분해, 5-tier + 칼리브레이션, bidirectional coverage, multi-round revision + early stopping(|Δ|<0.05), rule registry YAML 핫리로드.

**Gate**: 각 plan PR은 품질 회귀 금지 체크박스 통과 필수 (verified_citation_rate, Brier, hallucination_rate).

### Phase C — 조립 (Plan 4, Phase B 완료 후)
Plan 1/2/3의 산출물을 UI가 실시간으로 볼 수 있게 가공.
- `mcp_server.py` → `mcp/{server,tools/*,sessions,pipelines,schemas}.py` 분할
- Progressive SSE 이벤트: `stage_started/completed`, `crawl_progress_board`, `source_verified`, `verification_partial`, `revision_started/completed`
- SessionStore 프로토콜 (InMemoryStore + SqliteStore), Plan 1 캐시와 스키마 공유
- feature flags 단일 파일 집중 → `backend/app/feature_flags.py`

**Gate**: 체감 TTFT P50 ≤ 3s (첫 `stage_started` 또는 `crawl_progress_board`까지).

### Phase D — 위생 (Plan 5, 병렬)
- `backend/tests/scratch/` 승격/이관/삭제, `pytest -m live` 마커 도입

---

## 5. Feature Flag Topology

회귀 시 한 파일 수정으로 전량 off. `backend/app/feature_flags.py`.

| flag | 기본 | 용도 | 소속 plan |
|------|------|------|-----------|
| `BBS_CONCURRENCY` | 4 | 크롤 동시성 (1 → 직렬 회귀) | Plan 1 |
| `RETRIEVAL_MODE` | `hybrid` | `embedding` 회귀 옵션 | Plan 2 |
| `CONFIDENCE_TIERS` | `v2` | `v1` 3단계 회귀 | Plan 3 |
| `VERIFY_MORPH` | `0` | kiwipiepy 형태소 경로 | Plan 3 |
| `MAX_REVISION_ROUNDS` | 2 | 1로 내리면 revision 비활성 | Plan 3 |
| `SSE_EVENTS_VERSION` | `v1` | `v2` opt-in via `X-SSE-Events` 헤더 | Plan 4 |
| `SESSION_STORE` | `memory` | `sqlite` 옵션 | Plan 4 |

---

## 6. Quality Gate — 모든 Plan 공통 DoD 체크박스

각 plan 말미에 동일하게 박힘. Plan 0 baseline과 비교.

- [ ] 골든셋 `verified_citation_rate` 회귀 없음 (Plan 2 이후 +15%p)
- [ ] 골든셋 `hallucination_rate` 회귀 없음 (Plan 3 이후 ≤ 0.05)
- [ ] 골든셋 Brier score 회귀 없음 (Plan 3 이후 ≤ 0.10)
- [ ] `scripts/verify.sh --full` 통과
- [ ] `scripts/structure-check.py --strict` 위반 0건
- [ ] 해당 TD 상태 `resolved` + PR 링크·커밋 해시 기재
- [ ] PR ≤ 400 LOC (초과 시 내부 분할)

---

## 7. 결과물 파일맵

```
docs/
├── exec-plans/
│   ├── backend-enhancement-overview.md          (이 파일)
│   ├── active/
│   │   ├── backend-step4-pipeline-instrumentation-baseline.md   [신규]
│   │   ├── backend-step5-crawler-concurrent-cache-refactor.md   [신규]
│   │   ├── backend-step6-retrieval-hybrid-rerank.md             [신규]
│   │   ├── backend-step7-verification-multiround-tiers-registry.md [신규]
│   │   ├── backend-step8-mcp-modularization-progressive-sse.md  [신규]
│   │   └── backend-step9-scratch-tests-promotion.md             [신규 옵션]
│   └── tech-debt-tracker.md                      (TD-0001/2/3/4/8/9 → scheduled)
├── design-docs/
│   ├── index.md                                  (6건 목차 갱신)
│   ├── 00-quality-latency-baseline.md            [신규]
│   ├── 01-crawler-concurrency-and-cache.md       [신규]
│   ├── 02-hybrid-retrieval-and-domain-priors.md  [신규]
│   ├── 03-verification-tiers-and-multiround.md   [신규]
│   ├── 04-sse-progressive-events.md              [신규]
│   └── 05-mcp-session-store.md                   [신규]
├── product-specs/
│   └── overview.md                               (§9 KPI 목표치 반영)
└── harness/
    └── observability.md                          (§6 JSONL 계측 규약 추가)
```

---

## 8. Next Action

**Plan 0 (step4 baseline)를 맨 먼저 집행**. 계측 인프라가 들어가야 이후 Plan 1~4의 DoD 수치(기준선 대비 -%)를 측정할 수 있다.

착수 시:
1. `backend-step4-pipeline-instrumentation-baseline.md` 열어 `단계 1`부터 TaskCreate에 분해
2. Plan 0 착수 전 TD-0001/0002/0003/0004를 `scheduled` → `in-progress` 전환(2주 규칙)은 Plan 1/3/4 착수 시점에 한다
3. Plan 0 완료 후 Plan 1, 2, 3 병렬 브랜치 개시. Plan 4는 마지막에 조립

---

## 부록 — 관련 문서 링크
- Meta-plan 원본: `.claude/plans/starry-coalescing-patterson.md`
- 각 active plan: `docs/exec-plans/active/backend-step{4..9}-*.md`
- 각 design-doc: `docs/design-docs/{00..05}-*.md`
- KPI 정의: `docs/product-specs/overview.md#9-고도화-kpi-step4step8-목표치`
- 계측 규약: `docs/harness/observability.md#6-pipelinequality-메트릭-jsonl-step4-baseline-인프라`
