# 04 — Progressive SSE Event Contract

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead, frontend lead
**Related**: product-specs/overview, exec-plans/active/backend-step8-mcp-modularization-progressive-sse, design-docs/01, 02, 03

## Problem
현재 SSE 이벤트는 `stage_change / token / sources / confidence / final_answer / system_message` 6종. 사용자는 **Stage 1~5가 완료된 뒤 Stage 6 이후의 `token`부터** 첫 토큰을 보게 되어 체감 TTFT가 ~15s에 달한다. 크롤 진행 상황이나 개별 소스 검증이 끝나는 시점을 UI가 표시할 방법이 없어 "멈춘 것 같다"는 체감이 발생.

## Options
### Option A — 세분화된 progressive 이벤트 추가 (backward-compatible)
pros: 프런트는 모르는 이벤트만 drop하면 호환, 체감 TTFT 급감
cons: 이벤트 수 증가 → 네트워크 버스트. SSE 프레임 경량성으로 수용 가능

### Option B — WebSocket 전환
pros: 양방향, 프로토콜 유연
cons: 전면 재작성, 이번 사이클 범위 초과

### Option C — polling + chunked JSON
pros: 단순
cons: 레이턴시·대역폭 양쪽 손해

## Decision
**Option A**. 이벤트 스키마는 다음과 같이 고정(버저닝 `v1`).

### 이벤트 추가 목록 (기존 6종 외)

```json
// 1) stage 상세 (stage_change보다 세분)
{"type":"stage_started","stage":"crawling","ts":1712345678901,"req_id":"abc"}
{"type":"stage_completed","stage":"crawling","duration_ms":32100,"ok":true}

// 2) 크롤 보드별 진행
{"type":"crawl_progress_board","board":"질의응답","hits":12,"total_seen":47,"ts":...}

// 3) 단일 소스 검증 완료
{"type":"source_verified","source_id":"olta_bbs_12345",
 "status":"verified","confidence":0.81,"prior_type":"official_qna"}

// 4) 클레임 단위 검증 부분결과
{"type":"verification_partial","claim_id":"c_3",
 "state":"supported|partial|contradicted|unused","cited_sources":["olta_bbs_12345"]}

// 5) revision 트리거/완료 가시화
{"type":"revision_started","round":1,"reason":"low_coverage","from_confidence":0.58}
{"type":"revision_completed","round":1,"to_confidence":0.72,"delta":0.14}

// 6) baseline pipeline metric emit (Plan 0)
{"type":"pipeline_metric","stage":"rank","duration_ms":1800,"status":"ok"}
```

**기존 이벤트는 스키마 변경 없이 유지**. 새 이벤트는 `event: progress`(SSE event 필드) + `data: <json>`.

### 기본 OFF / opt-in
- 서버: 요청 헤더 `X-SSE-Events: v2` 또는 쿠키 `sse_events=v2` 인 경우에만 새 이벤트 emit
- 프런트 `chatStore`는 **모든 unknown type을 silent drop**하는 default guard 선행 구현 → 전환 중 에러 없음

### Playwright step3 시나리오 확장
- 시나리오 4·5에 `crawl_progress_board` 최소 1건, `source_verified` 최소 1건 assertion 추가
- 시나리오 4에 `verification_partial` ≥ 1건 + 최종 `confidence` 이벤트 도착 검증

### 레이트 스로틀
- `crawl_progress_board`: 보드당 최대 초당 2건 (서버 throttle)
- `verification_partial`: claim 1건당 최대 1회

## Consequences
- **+** 체감 TTFT P50 ≤ 3s (첫 `stage_started` 도달 기준)
- **+** 프런트 UX 개선 여지 확장 (보드별 진행 바, 소스 카드 점진 렌더)
- **+** verify 단계 진행률 가시화로 "60s 대기"의 체감 감소
- **−** SSE 연결이 평균 30~50% 더 많은 프레임을 흘림 — 측정 후 문제되면 throttle 상한 하향
- **−** 프런트 새 이벤트 핸들링 구현은 별도 frontend plan 트리거 필요 (본 문서가 계약)

## Follow-ups
- `exec-plans/active/backend-step8-mcp-modularization-progressive-sse.md`
- 프런트 진행 바 UI 구현: frontend-step2-progressive-sse (미생성)
- 이벤트 스키마 v2 → v3 필요 시 superseded 문서로 갈음
