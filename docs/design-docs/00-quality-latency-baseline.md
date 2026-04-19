# 00 — Quality × Latency Baseline

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead
**Related**: product-specs/overview, exec-plans/active/backend-step4-pipeline-instrumentation-baseline

## Problem
백엔드 `_run_full_pipeline`은 6개 Stage를 거쳐 응답을 생성하지만 **단계별 소요 시간이 로그 문자열에만 산재**한다. 품질 지표(`verified_citation_rate`, `hallucination_rate`, 신뢰도 tier 분포)는 아예 집계 지점이 없다. 이 상태로는 후속 고도화 plan들이 "P50 -60%" 같은 DoD 수치를 검증할 수 없다.

## Options
### Option A — OpenTelemetry 전면 도입
pros: 업계 표준, Trace/Metric 일원화, 프런트까지 확장 가능
cons: Collector/DB 인프라 추가, 로컬 개발 부담 상승, 2주 내 착수 불가

### Option B — 경량 JSONL + 데코레이터
pros: 의존성 0, 로컬 파일만으로 동작, 스크립트 질의 쉬움(`scripts/obs-query.py` 기존 존재)
cons: 분산 트레이싱 불가, 스키마 관리 수동

### Option C — structlog만 강화
pros: 기존 로그 재사용
cons: 필드 표준화 강제 불가, 파이프라인 전체 구조화 어려움

## Decision
**Option B**. `backend/app/observability/timing.py`에 `@stage_timed("<name>")` 데코레이터와 `quality_metric()` 컨텍스트 매니저를 두고, JSONL을 `observability/metrics/pipeline.jsonl`·`observability/metrics/quality.jsonl`에 append. 기존 `scripts/obs-query.py` 쿼리 인터페이스를 확장해 P50/P95 리포트 생성. 분산 트레이싱이 필요해지면 **superseded** 문서로 Option A로 전환.

### JSONL 스키마 (고정 계약)
```json
// pipeline.jsonl — Stage 1~6 각 호출마다 1 line
{"ts":"2026-04-17T10:12:03Z","req_id":"abc","stage":"crawling","duration_ms":34210,"status":"ok"}

// quality.jsonl — 답변 1건당 1 line
{
  "ts":"2026-04-17T10:13:02Z","req_id":"abc",
  "verified_citation_rate":0.82,
  "hallucination_rate":null,            // Plan 3 이전에는 null
  "coverage_score":null,
  "revision_triggered":true,
  "revision_rounds":1,
  "confidence_tier":"high","overall_confidence":0.78,
  "golden_set_id":"Q-003"                // 골든셋 호출일 때만
}
```

### Golden set
- `backend/tests/quality/golden_questions.yaml` — 20개 질문: 감면 10 / 부과 5 / 신고 3 / 매칭 없음 2
- 각 항목: `id`, `question`, `expected_source_types`(법령/판례/공식 Q&A), `must_contain_keywords`, `must_not_contain`
- 실행기: `scripts/bench-pipeline.sh --n 3 --report` — 각 질문 3회 호출, 결과를 `observability/reports/<YYYY-MM-DD>-baseline.md`에 P50/P95 표로 출력

## Consequences
- **+** 모든 후속 plan DoD에 수치 첨부 가능 (회귀 자동 탐지)
- **+** `obs-query.py` 단일 인터페이스 유지
- **−** JSONL 로테이션 정책을 수동 관리 (일 단위, 14일 보관)
- neutral: OTEL 전환 시 `stage_timed`를 OTEL span wrapper로 교체하면 호출부 변경 없음

## Follow-ups
- `exec-plans/active/backend-step4-pipeline-instrumentation-baseline.md`
- Plan 1~4의 DoD에서 본 문서의 JSONL 스키마를 참조
- 3개월 후 OTEL 도입 필요 여부 재평가 (분산 트레이스 요구 생기면)
