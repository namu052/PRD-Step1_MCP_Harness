# Product Spec — AI 지방세 지식인

**Status**: active
**Owner**: product / backend lead
**Last updated**: 2026-04-17

> Source of truth: 현재 이 저장소가 구현하는 제품의 기능·스택·파이프라인 요약.
> 변경 시에는 `docs/exec-plans/active/`에 exec-plan을 먼저 생성한 뒤 수정한다.

## 1. 문제 정의
지방자치단체 공무원이 지방세 질의에 대해 OLTA(지방세법령포털)·유권해석·예규를 교차 검증한 근거 기반 답변을 빠르게 얻도록 돕는다.

## 2. 스택
- Frontend: React 19 + Vite 8 + Zustand + Tailwind CSS 4 + MSW
- Backend: FastAPI + Playwright + OpenAI GPT-4o + FAISS
- Transport: SSE (`EventSource`)
- Agent surface: MCP stdio server (`backend/mcp_server.py`)

## 3. 프런트엔드 구조 (`frontend/src/`)
- Stores: `authStore.js`(GPKI), `chatStore.js`(messages/streaming/sources/confidence)
- Layout: 50:50 split — `ChatPanel`(좌) + `PreviewPanel`(우, source cards)
- SSE: `hooks/useSSE.js`
- Mock mode: `VITE_USE_MOCK` 플래그 + `mocks/handlers.js`
- Vite plugin: `gpkiPlugin()` — 로컬 파일시스템의 GPKI 인증서 로드

## 4. 백엔드 파이프라인 (`backend/app/`)
`/api/chat` (SSE) → 다단계 파이프라인:

| 단계 | 서비스 | 출력 이벤트 |
|------|--------|------------|
| Search planning | `services/search_service.py` | `stage_change` |
| Crawling | `services/crawler_service.py` (Playwright, OLTA) | `stage_change` |
| Embedding/Ranking | `services/embedding_service.py` (FAISS) | — |
| Evidence grouping | `services/evidence_group_service.py` | `sources` |
| Draft | `services/llm_service.py` | `token` |
| Verification | `services/verification/{source,content,grouped_answer}_verifier.py`, `verification_aggregator.py` | `confidence` |
| Final | `services/verification/final_generator.py` | `final_answer` |

SSE event types: `stage_change`, `token`, `sources`, `confidence`, `final_answer`, `system_message`.
UI stage sequence: `crawling → drafting → verifying → finalizing → done`.

## 5. 빌드/실행 명령
- Frontend: `cd frontend && npm install && npm run dev|build|lint`
- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Tests: `cd backend && pytest tests/ -v`
- MCP: `cd backend && python mcp_server.py`

## 6. 설정/비밀
- `backend/.env` 필수 (`OPENAI_API_KEY`, 프록시 변수 등). 예시는 `.env.example`.
- 런타임 튜닝값: `backend/app/config.py` (Pydantic Settings, 단일 소스).
- 프롬프트: `backend/app/prompts/*.py` — 단계별 파일 분리, 상수명 SCREAMING_SNAKE_CASE.

## 7. 코드 컨벤션 (요약)
자세한 규칙은 `docs/policies/GOLDEN_RULES.md`와 `docs/policies/STRUCTURE_RULES.md`를 본다.
- JS: 2-space 들여쓰기, 세미콜론 없음, ES modules
- React: 컴포넌트 PascalCase(`ChatPanel.jsx`), 도메인 디렉터리(`auth/chat/layout/preview`)
- Python: 서비스는 snake_case + `_service.py` 접미사
- 커밋 전: `scripts/verify.sh` (lint/type/test/구조검사 통합)

## 8. 테스트
- Backend: pytest + pytest-asyncio. Fixture/mock: `backend/tests/mocks/`.
- Frontend: 자동 테스트 없음. `npm run lint` + `npm run build` + `frontend/TODO.md` 수동 체크리스트.
- 구조/문서 검사: `scripts/structure-check.py`, `scripts/check-docs-freshness.py`.

## 9. 고도화 KPI (Step4~Step8 목표치)

| 지표 | baseline(추정) | 목표 | 측정 근거 |
|------|----------------|------|----------|
| TTFT P50 (첫 SSE 이벤트) | ~15s | **≤ 3s** | design-docs/04 progressive SSE |
| TTFT P95 | ~30s | **≤ 8s** | |
| 전체 응답 P50 | ~180s | **≤ 90s** | Step5 crawl 병렬화 + Step6 배치화 |
| 전체 응답 P95 | ~360s | **≤ 180s** | |
| `verified_citation_rate` | 미측정 | **≥ 0.85** | Step6 hybrid retrieval |
| `hallucination_rate` (bidirectional) | 미측정 | **≤ 0.05** | Step7 multi-round + coverage |
| confidence Brier score | 미측정 | **≤ 0.10** | Step7 5-tier calibration |

baseline 측정·검증 인프라는 `docs/exec-plans/active/backend-step4-pipeline-instrumentation-baseline.md`에서 확정한다.

## 10. 현재 한계·우선 tech debt
`docs/exec-plans/tech-debt-tracker.md` 참조.
