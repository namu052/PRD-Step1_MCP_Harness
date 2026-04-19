# [섹션 12] 관측 가능성 & UI 검증

## 1. Observability 아키텍처
```
App(Next.js)  ─┐                                            ┌─► docs/generated/metrics/*.md
App(FastAPI)  ─┼─► structured logs (JSON, stdout) ──────────┤
Playwright UI ─┘                                            │
                                                            ├─► logs/*.jsonl (RotatingFile)
  OpenTelemetry SDK (app)  ─► OTLP ─► local collector ──────┤
                                                            └─► observability/traces.db (sqlite, 14d)

Metrics  : FastAPI /metrics  + scripts/metrics-snapshot.py → docs/generated/metrics/weekly.md
Traces   : OTLP → local collector → sqlite (agent 질의용)
Logs     : JSON line. 필수 필드: ts, level, req_id, user_id?, stage, latency_ms, error?
UI       : Playwright screenshots + DOM dump → observability/ui-snapshots/
```

## 2. 데이터 흐름
1. 앱은 **구조화 로그**만 출력한다(JSON).
2. `observability/collector/` 안의 로컬 collector가 파일 로테이션을 담당한다.
3. 에이전트는 `scripts/obs-query.py --since 1h --stage verifying` 처럼 **스크립트**로만 질의한다. 원시 파일을 직접 grep하지 않는다.
4. 주간 snapshot은 `docs/generated/metrics/weekly.md`로 커밋된다(스크립트 전용 경로).

## 3. 에이전트 질의 예시
```bash
# 최근 한 시간 verifying 단계에서 p95 latency
scripts/obs-query.py --metric p95 --stage verifying --since 1h

# 특정 req_id의 트레이스
scripts/obs-query.py --trace <req_id>

# UI 스냅샷 diff (latest vs main)
scripts/ui-snapshot-diff.py --base main --head HEAD
```

## 4. UI 회귀 시나리오 10개 (Playwright)
1. GPKI 로그인 → 홈 진입
2. 질문 입력 → SSE 스트리밍 토큰 표시
3. source card 클릭 → 우측 preview 갱신
4. 신뢰도 배지(높음/중간/낮음) 표시
5. 크롤 진행률 바 0→100 이동
6. 빈 질문 제출 → 에러 메시지
7. 네트워크 끊김 → 재시도 토스트
8. 긴 답변 스크롤 + 소스 하이라이트 유지
9. 로그아웃 → 세션 스토리지 비움 재확인
10. 최종 답변 팝업 copy 버튼 동작

각 시나리오 실패 시 `observability/ui-snapshots/<date>/<scenario>.png`와 DOM dump 저장, PR 자동 코멘트.

## 5. 임시 환경 생성 → 검증 → 폐기
1. `scripts/worktree-up.sh <task>` 로 worktree + 포트 격리(backend 8100+, frontend 5200+)
2. `scripts/app-up.sh` 가 backend/frontend를 background 기동, health check 후 반환
3. `scripts/ui-regression.sh` 실행 → 10개 시나리오 + 스냅샷 저장
4. `scripts/obs-query.py --report` → 요약 리포트 생성
5. `scripts/worktree-down.sh <task>` → 포트/프로세스/worktree 정리, 아티팩트만 `observability/archive/`로 이동

**원칙**: "앱을 띄웠으면 반드시 내린다." 종료 훅이 실패하면 CI를 빨갛게 한다.

## 6. Pipeline/Quality 메트릭 JSONL (Step4+ baseline 인프라)

고도화 plan(Step4~Step8)의 DoD 수치를 강제하기 위해 **경량 JSONL 계측**을 병행한다. 계약은 `docs/design-docs/00-quality-latency-baseline.md` 고정.

### 파일 경로
- `observability/metrics/pipeline.jsonl` — Stage 1~6 각 호출 1 line
- `observability/metrics/quality.jsonl` — 답변 1건당 1 line
- `observability/reports/<date>-*.md` — P50/P95 + A/B 리포트 (사람 검토용)

### 스키마(발췌)
```json
{"ts":"...","req_id":"...","stage":"crawling","duration_ms":34210,"status":"ok"}
{"ts":"...","req_id":"...","verified_citation_rate":0.82,"hallucination_rate":null,
 "revision_triggered":true,"revision_rounds":1,"confidence_tier":"high",
 "overall_confidence":0.78,"golden_set_id":"Q-003"}
```

### 질의
- `scripts/obs-query.py --metric p50 --stage <name> --since 24h`
- `scripts/obs-query.py --report baseline`
- `scripts/bench-pipeline.sh --n 3 --report` — 골든셋(`backend/tests/quality/golden_questions.yaml`) 실행 후 리포트 생성

### 로테이션
- 일 단위, 14일 보관. 14일 초과 파일은 `scripts/obs-prune.py`가 `observability/archive/`로 이동
- JSONL은 `.gitignore` 대상. 리포트 md만 커밋
