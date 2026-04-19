# backend-step4-pipeline-instrumentation-baseline — dual-axis 고도화의 계측·기준선 인프라

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, design-docs/00-quality-latency-baseline

## 1. Why (배경·문제)
후속 plan(Step5~Step8)의 DoD가 "crawl P50 -60%", "verified_citation_rate +15%p" 같은 **수치적 회귀 방지**를 강제한다. 현재 상태는 stage별 소요 시간이 로그 문자열에만 있고 품질 지표 집계 지점이 없어 baseline을 찍을 수 없다. 고도화 전에 계측 인프라와 골든셋을 먼저 확정해야 이후 plan들이 "실제로 좋아졌는가"를 증명할 수 있다.

## 2. Scope
### In
- `backend/app/observability/timing.py` — `@stage_timed("<name>")` 데코레이터, `quality_metric()` 컨텍스트 매니저
- `_run_full_pipeline` Stage 1~6 전부에 데코레이터 부착(행동 변경 0, 로깅만)
- `backend/tests/quality/golden_questions.yaml` — 20개 질문(감면 10 / 부과 5 / 신고 3 / 매칭없음 2)
- `scripts/bench-pipeline.sh` — 골든셋 N회 실행, P50/P95 리포트 생성
- `scripts/obs-query.py` 확장: `--metric p50|p95 --stage <name> --since <dur>`, `--report baseline`
- baseline 리포트 `observability/reports/<date>-baseline.md` 1회 작성·커밋
### Out
- 코드 동작 변경
- OpenTelemetry 도입 (design-doc 00 Option A는 deferred)
- 실제 A/B 비교(후속 plan이 수행)

## 3. Definition of Done
- [ ] `@stage_timed`로 Stage 1~6 전부 계측, JSONL 스키마(design-doc 00) 준수
- [ ] `observability/metrics/pipeline.jsonl` / `quality.jsonl` 에 실 데이터 1건 이상 기록 확인
- [ ] `golden_questions.yaml` 20개, 각 항목에 `id/question/expected_source_types/must_contain_keywords/must_not_contain` 필드 완비
- [ ] `scripts/bench-pipeline.sh --n 3 --report` 실행 시 P50/P95 표 출력 → 첫 baseline을 `observability/reports/2026-04-<dd>-baseline.md`로 커밋
- [ ] `scripts/obs-query.py --report baseline` 스모크 통과
- [ ] `scripts/verify.sh` 통과, 신규 테스트 `tests/observability/test_timing.py` 추가
- [ ] PR ≤400 LOC

## 4. 구현 단계
1. `backend/app/observability/timing.py` 작성 (데코레이터 + JSONL writer, 비동기 함수 지원)
2. `_run_full_pipeline` Stage 1~6 데코레이터 부착 (`mcp_server.py:657~887` 영역)
3. `golden_questions.yaml` 구성 — 기존 `backend/tests/mocks/` 참고하여 질문군 선별
4. `scripts/bench-pipeline.sh` + `scripts/obs-query.py` 확장 (P50/P95 집계)
5. 로컬에서 1회 실행 → baseline 리포트 커밋
6. `docs/harness/observability.md`에 JSONL 경로·스키마 섹션 추가

## 5. 위험 & 롤백
- 위험: 동기/비동기 함수 혼재로 데코레이터 적용 누락 → `asyncio.iscoroutinefunction` 분기로 해결
- 위험: JSONL 파일 크기 폭증 → 일 단위 로테이션 + 14일 보관 (design-doc 00)
- 롤백: 데코레이터 제거 + JSONL 디렉터리 삭제로 완전 원복

## 6. 검증 계획
- 단위: `tests/observability/test_timing.py` — 동기/비동기/예외 경로 3건
- 통합: 로컬에서 `scripts/bench-pipeline.sh --n 1` 실행 후 JSONL 1건 이상 확인
- 수동: baseline 리포트가 사람이 읽어 납득 가능한 수치(P50 < P95) 인지

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 후속 Step5~Step8의 필수 선행.
- 2026-04-18 — Gate A 부분 수행(A-2, A-5): PASS — `observability/reports/2026-04-18-gate-a.md`. `scripts/obs-prune.py` 신규 추가(§6 관측 규약 이행). A-1/A-3/A-4 는 GPKI 세션 대기
- 2026-04-18 — infra 구현 완료:
  - `backend/app/observability/timing.py` (`@stage_timed` 데코레이터 + async/sync 컨텍스트 매니저 + `quality_metric()`)
  - `backend/mcp_server.py:657~890` Stage 1~6 async with 블록으로 계측 (행동 변경 0)
  - `backend/tests/quality/golden_questions.yaml` 20문항 (감면 10 / 부과 5 / 신고 3 / 매칭없음 2)
  - `scripts/bench-pipeline.sh`, `scripts/obs-query.py` (--metric, --report baseline 확장)
  - `backend/tests/observability/test_timing.py` 6건 green
  - `observability/reports/2026-04-18-baseline.md` 작성 — **infra-only 상태** (GPKI 미탑재 환경이라 실측 수치 빈 표). Gate A 의 §4 에 "인증 환경에서 `scripts/bench-pipeline.sh --n 3 --report` 1회" 액션 명시
  - 회귀: 기존 테스트 57건 중 56건 green, 1건 `test_chat_pipeline_stream_order` 선존 실패(stage 이름 불일치, Plan 0 무관)
- 2026-04-18 — Plan 1/2/3/5 Phase B 착수 후 회귀 확인:
  - backend 전체 81 passed (test_chat_pipeline_stream_order 선존 실패 1건 동일 유지 — Plan 0/1/2/3/5 무관)
  - structure-check 잔존 위반은 TD-0001(mcp_server.py, Plan 4) / TD-0002(crawler_service.py, Plan 1 PR#2~5 이월) / TD-0005·TD-0006·TD-0007(out of scope) 로 축소
  - Phase B 결과: TD-0003 / TD-0004 / TD-0008 / TD-0009 resolved; TD-0002 in-progress
