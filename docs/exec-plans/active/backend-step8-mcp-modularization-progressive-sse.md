# backend-step8-mcp-modularization-progressive-sse — MCP 분할 · SessionStore · progressive SSE (체감 TTFT ≤ 3s)

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, design-docs/04-sse-progressive-events, design-docs/05-mcp-session-store, active/backend-step5, step6, step7

## 1. Why (배경·문제)
`mcp_server.py`(1003줄, TD-0001)는 단일 파일에 9개 Tool + 캐시 + 파이프라인 로직이 뭉쳐 있어 Step5~7의 산출물(새 verification 스키마, SessionStore, SQLite 캐시)을 조립하기에 구조 부채가 크다. UI 측면에서도 현재 SSE는 Stage 1~5가 끝난 뒤에야 `token`이 시작되어 체감 TTFT ~15s. Step5~7을 품고 **체감 TTFT를 Stage 1 시작 직후(≤3s)** 로 끌어내린다.

## 2. Scope
### In
- `mcp_server.py` → `mcp/{server,tools/*,sessions,pipelines,schemas}.py` 분할. 퍼사드 ≤150줄. 기동 스크립트 무수정 (TD-0001)
- `SessionStore` 프로토콜 + `InMemoryStore`/`SqliteStore` (design-doc 05). Step5의 `crawl_cache.db`와 **같은 파일에 namespace 공유**
- Progressive SSE 이벤트(design-doc 04) emit: `stage_started/completed`, `crawl_progress_board`, `source_verified`, `verification_partial`, `revision_started/completed`, `pipeline_metric`
- opt-in 헤더 `X-SSE-Events: v2` 기반 분기. 기본 off
- `backend/app/feature_flags.py`로 모든 flag 집중: `RETRIEVAL_MODE`, `CONFIDENCE_TIERS`, `VERIFY_MORPH`, `MAX_REVISION_ROUNDS`, `BBS_CONCURRENCY`, `SSE_EVENTS_VERSION`
- 9개 Tool I/O 스키마를 `mcp/schemas.py` pydantic 모델로 일원화
### Out
- 실제 Redis 도입 (스텁만)
- 프런트 UI 레이아웃 변경 (계약만 고정, 구현은 frontend plan)

## 3. Definition of Done
- [ ] 체감 TTFT (첫 `stage_started` 또는 `crawl_progress_board` 이벤트 도달) P50 ≤ 3s
- [ ] `mcp_server.py` ≤150줄 퍼사드 (TD-0001 resolved)
- [ ] Playwright step3 시나리오 4·5에 `crawl_progress_board`, `source_verified`, `verification_partial` 각 ≥1건 assertion 추가
- [ ] 기존 프런트가 `X-SSE-Events` 미전송 시 기존 6종 이벤트만 수신(회귀 0건)
- [ ] `scripts/verify.sh --full` + MCP client smoke(`python -m backend.mcp_server --smoke`) 통과
- [ ] feature flag 7종이 `feature_flags.py` 한 파일에 집중, 단위 테스트 통과
- [ ] 내부 PR 3개 분할: A) sessions/schemas B) tools/* C) pipelines+SSE. 각 ≤400 LOC
- [ ] `tech-debt-tracker.md` TD-0001 `resolved`

## 4. 구현 단계
1. PR-A: `mcp/sessions.py` (`SessionStore` + `InMemoryStore` + `SqliteStore`) + `mcp/schemas.py`(Tool I/O 9종). `_MCPSession`→`InMemoryStore` 리프레이즈, 동일성 테스트
2. PR-B: `mcp/tools/*.py` 9개 분리. 퍼사드 `mcp_server.py`는 FastMCP 진입 + re-export
3. PR-C: `mcp/pipelines.py` — `_run_search_pipeline`/`_run_full_pipeline`/`_run_verification` 이전. progressive SSE emit 포인트 추가. `feature_flags.py` 도입 + 기존 flag 이관
4. 프런트 chatStore에 **default-drop 가드** 먼저 배포(별도 PR이지만 frontend-side로 태깅)
5. Playwright step3 시나리오 확장 (assertion 추가)
6. 최종: 체감 TTFT 측정 리포트 `observability/reports/<date>-ttft.md`

## 5. 위험 & 롤백
- 위험1: 프런트가 unknown event 에러 → chatStore default-drop 가드를 PR-A 이전에 배포. 배포 순서 고정
- 위험2: SqliteStore 쓰기 경합 → WAL + 배치 쓰기, 운영 중 `SESSION_STORE=memory`로 폴백
- 위험3: tool name 리스트 변경 → 기동 시 tool name 해시 로깅으로 회귀 감지
- 롤백: `SSE_EVENTS_VERSION=v1` + `SESSION_STORE=memory` 환경변수로 이전 동작 복원. 퍼사드 원복은 single revert

## 6. 검증 계획
- 단위: `tests/mcp/test_session_store.py`, `test_pipelines.py`, `test_feature_flags.py`
- 통합: `scripts/verify.sh --full`, MCP smoke
- UI: Playwright step3 시나리오 4·5 확장
- 성능: TTFT 리포트 + Step4 baseline과 비교

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 선행: Step5/6/7 산출물 확정. TD-0001 scheduled.
- 2026-04-18 — PR#1 (인프라 only, facade 분할 이월) 착수·완료:
  - `backend/app/mcp/__init__.py` 패키지 신설
  - `backend/app/mcp/schemas.py` — 9개 Tool 입력 pydantic 모델(`CheckOltaLoginRequest` … `AskLocalTaxRequest`) + `ToolResult` 제네릭 응답 래퍼 + `TOOL_REQUEST_MODELS` 레지스트리. `model_config = ConfigDict(extra="forbid", frozen=True)` 로 오타·의도치 않은 필드 차단
  - `backend/app/mcp/sessions.py` — `SessionStore` Protocol + `InMemoryStore`(dict + TTL 300s, 기존 `_MCPSession` 동등) + `SqliteStore`(`backend/data/mcp_session.db`, `(bucket, k)` composite PK, JSON 직렬화, pydantic `model_dump` fallback). `get_session_store()` 팩토리가 `feature_flags.session_store` 를 따라 선택
  - `backend/app/mcp/pipeline_events.py` — 진행형 이벤트 JSONL emit 훅 (`observability/metrics/events.jsonl`). `feature_flags.sse_events_version=="v2"` 일 때만 기록, `v1` 이면 no-op. 헬퍼 `stage_started/completed`, `crawl_progress_board`, `source_verified`, `verification_partial`, `revision_started/completed` + `pipeline_metric` 타입 화이트리스트
  - 단위 37건 green (`test_mcp_schemas.py` 11 + `test_mcp_sessions.py` 16 + `test_pipeline_events.py` 10). 전체 backend 테스트 121 passed (pre-existing `test_chat_pipeline_stream_order` 1건 선존 실패 — 이 plan PR#2 대상)
  - **행동 변경 0**: `mcp_server.py` 는 아직 이 인프라를 호출하지 않음. `_MCPSession` 그대로 동작
  - **TD-0001 상태**: 여전히 `scheduled` (facade 분할은 PR#2 이월). 완료 시 resolved 전환
  - **잔여 (PR#2~3, live MCP smoke 필요)**:
    - PR#2: `mcp_server.py` → `backend/app/mcp/server.py` + `tools/*.py` 9개 분할, 퍼사드 `backend/mcp_server.py` ≤150줄 (TD-0001 resolve)
    - PR#3: `mcp/pipelines.py` 에 `_run_search_pipeline/_run_full_pipeline/_run_verification` 이전 + Stage 경계마다 `pipeline_events.stage_started/completed` 호출 삽입. `_session` → `get_session_store()` 교체
    - Playwright step3 시나리오 4·5 에 `crawl_progress_board/source_verified/verification_partial` assertion 추가. chatStore default-drop 가드 선배포
    - TTFT 측정 리포트 `observability/reports/<date>-ttft.md` (live MCP client 필요)
