# 백엔드 고도화 — 사용자 검증 플랜

**Status**: active
**Created**: 2026-04-18
**Owner**: backend lead + product
**Related**: exec-plans/backend-enhancement-overview, exec-plans/active/backend-step4~step9, design-docs/00-quality-latency-baseline

> 자동 CI(`scripts/verify.sh`, 골든셋, structure-check)는 **코드 회귀**를 막는다.
> 이 문서는 그 위에서 **사람이 직접 확인해야 하는 항목**만 3개 Gate로 고정한다.
> 각 Gate는 **PASS/FAIL 이분법**이며, FAIL이 하나라도 있으면 다음 Phase로 넘어가지 않는다.

---

## Gate 개요

```
Plan 0 완료 ─► [Gate A] 측정 인프라 검증 ─► PASS시 Phase B 개시
                                             │
Plan 1/2/3/5 완료 ─► [Gate B] 이중축 KPI 검증 ─► PASS시 Plan 4 착수
                                                  │
Plan 4 완료 ─► [Gate C] 전체 고도화 최종 검증 ─► PASS시 production 전환
```

| Gate | 대상 | 소요 | 주체 |
|------|------|------|------|
| A | Plan 0 | 30분~1시간 | backend lead |
| B | Plan 1+2+3+5 | 2~3시간 | backend lead + QA |
| C | Plan 4 (최종) | 4~6시간 + 48h 체감 모니터 | backend + frontend + product |

---

# Gate A — Plan 0 완료 후 검증 (측정 인프라)

**목표**: 이후 Phase의 "baseline 대비 -X%" 주장이 신뢰 가능한지 확인. 행동 변경은 없으므로 **계측 infra의 단단함**만 본다.

## A-1. JSONL 계측 동작 확인
- [ ] `backend/` 백엔드 기동 후 1회 질의 실행
- [ ] `observability/metrics/pipeline.jsonl` 에 Stage 1~6 **각 1 line** 출력 확인
  - 필수 필드: `ts, req_id, stage, duration_ms, status`
  - `stage` 값: `search_planning, crawling, ranking, evidence_grouping, drafting, verifying`
- [ ] `observability/metrics/quality.jsonl` 에 답변 1건당 1 line 출력
  - 필수: `req_id, verified_citation_rate, confidence_tier, overall_confidence`
  - Plan 3 미완성이므로 `hallucination_rate=null` 허용

## A-2. Golden Set 적정성 (사람 검수)
- [ ] `backend/tests/quality/golden_questions.yaml` 20문항 전수 읽기
- [ ] 카테고리 비율 확인: **감면 10 / 부과 5 / 신고 3 / 매칭없음 2**
- [ ] 각 질문이 실제 공무원 업무 질의를 대표하는지 사람 판단
  - FAIL 시: 대표성 떨어지는 질문은 product 팀이 교체 후 재측정

## A-3. bench-pipeline.sh 재현성
- [ ] `scripts/bench-pipeline.sh --n 3 --report` 2회 연속 실행
- [ ] 두 리포트의 P50/P95 차이가 ±10% 이내 (환경 안정성)
- [ ] 리포트가 `observability/reports/<date>-baseline.md` 경로에 고정 파일명으로 저장되는지

## A-4. Baseline 수치 commit
- [ ] baseline 리포트가 git에 커밋됐는지 (`observability/reports/` 는 리포트 md만 추적)
- [ ] 리포트 내 P50/P95 수치가 product-specs §9 "baseline(추정)" 컬럼 수치와 같은 자릿수인지
  - 추정: TTFT P50 ~15s, 전체 P50 ~180s
  - **실측이 추정과 50% 이상 다르면** 이후 모든 plan 목표치 재협의 필요

## A-5. 로테이션 동작 확인
- [ ] `scripts/obs-prune.py` 를 `--dry-run` 으로 실행 → 14일 로직 정상 판단
- [ ] JSONL 파일이 `.gitignore` 에 들어있는지 확인 (리포트 md만 커밋되어야 함)

## A Gate 결론
모든 항목 ✅ → Phase B (Plan 1/2/3/5) 병렬 개시
하나라도 ❌ → Plan 0 재작업. 측정 없는 최적화는 진행하지 않음.

---

# Gate B — Plan 1+2+3+5 완료 후 검증 (이중축 KPI)

**목표**: Latency↓ + Quality↑ 양 축이 **Plan 0 baseline 대비 목표치 달성** + 기존 기능 회귀 없음 확인.

## B-1. Latency 목표 (Plan 1, 2 기여)
baseline 리포트와 Phase B 종료 리포트를 diff.

- [ ] **crawl 단계 P50**: baseline 대비 **-60% 이상** (Plan 1 DoD)
- [ ] **SQLite 캐시 히트 시 crawl P50 ≤ 3s** (2회 연속 동일 질의 재현)
- [ ] **ranking 단계 P50**: baseline 대비 **-50% 이상** (Plan 2 DoD)
- [ ] **전체 응답 P50 ≤ 120s** (최종 목표 90s는 Plan 4 포함해서 달성하면 됨, 여기선 중간 지표)

## B-2. Quality 목표 (Plan 2, 3 기여)
골든셋 20문항 재실행 후 리포트 비교.

- [ ] `verified_citation_rate`: baseline 대비 **+15%p 이상** 또는 **≥ 0.85 절대치**
- [ ] `hallucination_rate` (bidirectional): **≤ 0.05**
- [ ] `confidence` Brier score: **≤ 0.10**
- [ ] `revision_trigger_rate` 가시화된 수치로 집계되고 있음 (값 자체는 회귀 금지 조건)
- [ ] 특정 카테고리 편향 없음: 감면/부과/신고/매칭없음 4 카테고리 각각 Brier ≤ 0.15

## B-3. 구조 리팩터 검증 (TD 해소)
- [ ] `scripts/structure-check.py --strict` 위반 0건
- [ ] tech-debt-tracker.md 에서 **TD-0002, 0003, 0004, 0008, 0009** 전부 `resolved` + PR/커밋 해시 있음
- [ ] `backend/app/services/crawler_service.py` ≤ 150줄 (퍼사드만)
- [ ] `backend/app/services/verification/verification_aggregator.py:aggregate` ≤ 50줄
- [ ] `backend/tests/scratch/` 비워지거나 예외 규칙 명시 문서화

## B-4. 기존 기능 회귀 없음
- [ ] `scripts/verify.sh --full` 통과
- [ ] `pytest backend/tests/ -v` 전부 green (live 마커 제외)
- [ ] 프런트 `npm run lint && npm run build` 통과
- [ ] 기존 Playwright 10개 시나리오(observability.md §4) 전부 pass

## B-5. Feature Flag 롤백 리허설 (필수)
각 flag를 실제로 off 시키고 1회 질의 돌려 확인. 이상 없으면 복구.

- [ ] `BBS_CONCURRENCY=1` → 크롤 직렬 회귀, 에러 없음
- [ ] `RETRIEVAL_MODE=embedding` → BM25 꺼짐, 기존 embedding-only 동작
- [ ] `CONFIDENCE_TIERS=v1` → 3단계 라벨로 복귀, 프런트 `ConfidenceBadge` 정상
- [ ] `MAX_REVISION_ROUNDS=1` → revision 단일 라운드 회귀
- [ ] `VERIFY_MORPH=0` → kiwipiepy 경로 미사용, 기본 regex 경로 정상

## B-6. 사람 체감 샘플링 (UAT 경량)
product 팀 또는 실제 사용자 1~2명이 **골든셋 아닌 실업무 질의 10개** 수동 질의.

- [ ] Top-5 소스 순서가 "법령 > 유권해석 > 예규 > 일반" 순으로 합리적
- [ ] 도메인 priors YAML 가중치에 대한 업무 담당자 승인
- [ ] 5-tier 라벨의 업무적 납득성 (very_high/high/medium/low/very_low)
- [ ] 프런트 `ConfidenceBadge` 5→3 legacy 매핑 표가 사람 눈에 합리적

## B-7. 외부 의존성 건강도
- [ ] OLTA rate-limit 이력: 최근 24시간 403/세션만료 ≤ 1건 (`BBS_CONCURRENCY=4` 상태에서)
- [ ] 캐시 stale 타이밍: 1시간 경과 후 재질의 시 fresh 응답 (`x-crawl-cache-age` 헤더 0)
- [ ] OpenAI API 비용 delta ≤ +20% (임베딩 배치화로 오히려 감소해야 정상)

## B Gate 결론
7개 섹션 모두 PASS → Plan 4 착수 허가
Quality 3지표 중 1개라도 회귀 → 해당 flag off → 원인 조사 → 재작업 후 재검증
Latency 지표 회귀 → 조건부 허용(Plan 4에서 TTFT가 덮을 가능성). 단, 절대치 baseline 대비 +10% 이상 악화면 FAIL.

---

# Gate C — Plan 4 완료 후 전체 고도화 최종 검증

**목표**: 이중축 고도화의 최종 제품 품질 확인. production 전환 가능 여부 판정.

## C-1. 체감 TTFT (핵심 사용자 지표)
**사람이 직접** Chrome DevTools Network 탭 열고 측정. Playwright 자동 수치만 신뢰 금지.

- [ ] 첫 SSE 이벤트(`stage_started` 또는 `crawl_progress_board`) **P50 ≤ 3s**
- [ ] 첫 SSE 이벤트 **P95 ≤ 8s**
- [ ] 10회 수동 실측 중 "느리다" 체감 0건
- [ ] 프런트 Loading UI가 Stage 전환별로 **시각적으로 변화** (단순 스피너 회전만 X)

## C-2. 전체 KPI 목표치 달성 (product-specs §9 대응)
골든셋 + 실업무 질의 혼합 N=60 대량 실행 후 리포트.

| 지표 | 목표 | 확인 |
|------|------|------|
| TTFT P50 | ≤ 3s | [ ] |
| TTFT P95 | ≤ 8s | [ ] |
| 전체 응답 P50 | ≤ 90s | [ ] |
| 전체 응답 P95 | ≤ 180s | [ ] |
| `verified_citation_rate` | ≥ 0.85 | [ ] |
| `hallucination_rate` | ≤ 0.05 | [ ] |
| Brier score | ≤ 0.10 | [ ] |

## C-3. SSE 이벤트 계약 검증 (design-doc 04)
- [ ] `X-SSE-Events: v2` 헤더 요청 시 새 이벤트 전부 전송
  - `stage_started, stage_completed, crawl_progress_board, source_verified, verification_partial, revision_started, revision_completed, pipeline_metric`
- [ ] 헤더 없거나 `v1` 요청 시 **기존 이벤트만** 전송 (하위 호환)
- [ ] 프런트 unknown event 가드: 임의 payload 주입 시 `chatStore` default-drop 정상
- [ ] Playwright step3 시나리오 4~5가 새 이벤트 assertion 통과

## C-4. Playwright UI 회귀 10 시나리오 + 사람 눈 검사
자동 스냅샷 diff만 신뢰 금지. **사람이 직접 클릭**.

- [ ] GPKI 로그인 → 홈
- [ ] 질문 입력 → SSE 스트리밍 토큰 표시
- [ ] source card 클릭 → 우측 preview 갱신
- [ ] 신뢰도 배지 5-tier 정상 표시 (또는 legacy 3-tier 매핑)
- [ ] 크롤 진행률 바가 **보드별로** 증가 (Plan 4 `crawl_progress_board` 이벤트 반영)
- [ ] 빈 질문 제출 → 에러 메시지
- [ ] 네트워크 끊김 → 재시도 토스트
- [ ] 긴 답변 스크롤 + 소스 하이라이트 유지
- [ ] 로그아웃 → 세션 스토리지 비움
- [ ] 최종 답변 copy 버튼 동작

## C-5. SessionStore 전환 검증 (design-doc 05)
- [ ] `SESSION_STORE=memory` → 기존 동작 동일 (InMemoryStore)
- [ ] `SESSION_STORE=sqlite` → 백엔드 재시작 후 세션/캐시 유지
- [ ] SQLite WAL 모드 활성, 동시 10 요청에서 lock 에러 0건
- [ ] Plan 1 crawler 캐시와 네임스페이스 분리되어 상호 오염 없음

## C-6. 전체 Feature Flag 롤백 전수 리허설
**production 사고 시나리오 대비**. 각 flag off → 1회 질의 → on 복구 전수.

- [ ] `SSE_EVENTS_VERSION=v1` → 기존 UI 동작
- [ ] `SESSION_STORE=memory` → SqliteStore 꺼도 정상
- [ ] B-5의 5개 flag도 재확인
- [ ] **전량 off 시나리오**: 모든 flag를 Plan 0 이전 값으로 되돌리면 "Plan 0만 적용된 상태"와 동등하게 동작

## C-7. 구조·문서 최종
- [ ] `mcp_server.py` ≤ 150줄 (TD-0001 resolved)
- [ ] `scripts/structure-check.py --strict` 위반 0건
- [ ] `scripts/check-docs-freshness.py` stale 0건
- [ ] tech-debt-tracker.md: TD-0001 `resolved` + PR 링크
- [ ] 6개 design-doc Status `accepted`
- [ ] 6개 active plan을 `docs/exec-plans/completed/` 로 이동
- [ ] product-specs/overview.md §9 KPI가 **목표치**에서 **실측 달성치**로 업데이트

## C-8. 48시간 체감 모니터 (운영 전환 전 관찰)
배포 직후 48시간 모니터링.

- [ ] OLTA rate-limit 경고 0건
- [ ] 에러율 Plan 0 baseline 대비 +0.5%p 이내
- [ ] p99 응답 시간 outlier(>300s) 빈도 Plan 0 대비 감소 또는 동등
- [ ] 사용자 피드백(있다면) 부정적 응답 0건
- [ ] OpenAI 비용 일일 합계 베이스라인 대비 -10%~+20% 범위

## C-9. Production 전환 승인 문서
- [ ] Gate A/B/C 결과 리포트 (`observability/reports/<date>-gate-c-final.md`)
- [ ] meta-plan(`.claude/plans/starry-coalescing-patterson.md`) 및 `backend-enhancement-overview.md` 에 완료 도장 (Status: completed)
- [ ] 사후 회고 1페이지 작성 (무엇이 잘 됐고, 무엇이 예상과 달랐는지 → 다음 고도화 사이클 입력)

## C Gate 결론
9개 섹션 모두 PASS → production 전환
체감 TTFT 또는 Quality 3지표 중 FAIL → 해당 영역 flag off로 부분 롤백, 원인 exec-plan 추가 등록
전체 FAIL → meta-plan 재검토 워크숍 (architect + backend lead + product)

---

## 부록 A — Gate 실행 체크리스트 템플릿

각 Gate 실행 시 아래 템플릿을 복사해 `observability/reports/<date>-gate-{A|B|C}.md` 에 저장.

```markdown
# Gate {X} 검증 리포트 — <date>

**검증자**: <name>
**환경**: local / staging / production
**대상 PR / 커밋**: <link>
**Plan 0 baseline 리포트**: <link>

## 결과 요약
- PASS 항목: N / M
- FAIL 항목: <list with reason>

## 수치 diff (해당 Gate에 필요한 지표만)
| 지표 | baseline | 이번 | Δ | 목표 충족 |
|------|----------|------|---|-----------|
| ... | ... | ... | ... | ✅/❌ |

## 인간 판단 항목 (주관 평가)
- <항목>: <한 줄 평>

## 이슈 / 후속 액션
- [ ] <액션 1>
- [ ] <액션 2>

## 다음 단계
- PASS → <다음 Phase 개시>
- FAIL → <롤백 또는 재작업 plan 링크>
```

---

## 부록 B — FAIL 발생 시 롤백 결정 트리

```
FAIL 발견
  │
  ├─ 특정 feature flag 영역인가?
  │    ├─ YES → 해당 flag off → 즉시 서비스 복구 → 원인 조사 → 수정 PR
  │    └─ NO  → 다음 질문
  │
  ├─ 구조/리팩터 영역인가?
  │    ├─ YES → 이전 커밋으로 revert 검토 → backend lead 판단
  │    └─ NO  → 다음 질문
  │
  └─ 측정 지표 자체가 틀렸는가?
       ├─ YES → Plan 0 계측 로직 수정 → 재측정
       └─ NO  → meta-plan 재검토 소집
```

---

## 부록 C — 역할 분담

| 역할 | Gate A | Gate B | Gate C |
|------|--------|--------|--------|
| backend lead | 주도 | 주도 | 참여 |
| frontend lead | - | B-4 참여 | C-3, C-4 주도 |
| product | A-2 주도 | B-6 주도 | C-1, C-8 참여 |
| QA | - | B-4, B-5 참여 | C-4 전담 |
| architect | - | - | C-9 회고 |
