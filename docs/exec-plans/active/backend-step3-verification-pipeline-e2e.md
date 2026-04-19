# backend-step3-verification-pipeline-e2e — 5단계 검증 스테퍼/신뢰도 브라우저 검증

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, references/archived/backend-todo-step3.md, active/backend-step2-browser-e2e

## 1. Why
Step 3 검증 파이프라인(`source/content/grouped_answer_verifier`, `aggregator`, `final_generator`)과 프런트 `StatusStepper` 5단계/`ConfidenceBadge`는 구현·pytest 통과 상태. 남은 것은 브라우저에서 SSE 이벤트 순서와 신뢰도 표시를 눈으로 확인하는 한 항목뿐이다. 이를 자동화한다.

## 2. Scope
### In
- Playwright 시나리오: 5단계 스테퍼 전환 (`crawling → drafting → verifying → finalizing → done`) 순서 assertion
- `ConfidenceBadge`가 "높음/보통/낮음" 중 하나로 표시되는지 assertion
- `sources` 이벤트에 `confidence` 필드 포함 스냅샷 저장
- 검증 실패 경로: 할루시네이션 초안 강제 주입 → 경고 메시지 표시 확인
### Out
- 새로운 검증 로직 추가
- 성능 최적화

## 3. Definition of Done
- [ ] Playwright 시나리오 `step3-verification.spec.js` 추가 (정상/할루시네이션 2건)
- [ ] SSE 이벤트 순서 assertion 포함
- [ ] confidence 필드 스냅샷 아티팩트
- [ ] `scripts/verify.sh` 통과
- [ ] `backend/TODO_STEP3.md` 미완 항목 제거

## 4. 구현 단계
1. mock 경로로 할루시네이션 초안(`src_999`) 재현 fixture 재활용
2. Playwright 시나리오 2건 작성
3. SSE 이벤트 순서 검증을 위해 `chatStore`의 이벤트 로그 노출(dev 전용 window bridge)
4. UI regression 번호 4–5로 등록

## 5. 위험 & 롤백
- 위험: dev 전용 window bridge가 프로덕션에 누출 → `if (import.meta.env.DEV)` 가드
- 롤백: 테스트 파일 삭제만으로 복구

## 6. 검증 계획
- `scripts/ui-regression.sh --scenarios 4,5`
- `observability/ui-snapshots/<date>/step3-*.png`

## 7. 일지
- 2026-04-17 — active 등록 (원본: backend/TODO_STEP3.md)
