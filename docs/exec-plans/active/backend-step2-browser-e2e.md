# backend-step2-browser-e2e — Step 2 브라우저 통합 E2E 수동 검증 마무리

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude | codex (UI는 claude가 주도)
**Autonomy level**: L2
**Related**: product-specs/overview, references/archived/backend-todo-step2.md

## 1. Why (배경·문제)
Step 2 백엔드·프론트엔드 연동은 코드 레벨에서는 완료되었으나, 원본 TODO(`backend/TODO.md`)의 "브라우저 통합 플로우 확인"과 "시나리오 테스트 및 에러 처리 점검" 두 항목만 남아있다. Playwright 기반 자동화로 잔여 수동 검증을 대체한다.

## 2. Scope
### In
- 백엔드(`uvicorn`) + 프런트엔드(`npm run dev`) 동시 기동 후 통합 플로우 자동화 1회
- 시나리오 3건: (a) 취득세 감면 / (b) 재산세 납부 / (c) 매칭 없는 질문
- 네트워크 끊김·세션 만료·400/500 응답 프론트 처리 확인
### Out
- 실제 GPKI 인증서 사용(프론트 step1 plan으로 분리)
- OLTA 라이브 크롤(`backend/tests/scratch/test_bbs_live.py` 승격 별도 plan)

## 3. Definition of Done
- [ ] `scripts/app-up.sh`로 dev 2종 기동
- [ ] Playwright 시나리오 3건 추가 → `observability/ui-snapshots/<date>/step2-*.png`
- [ ] 401/500 에러 케이스 스냅샷 포함
- [ ] `scripts/verify.sh` 통과
- [ ] `backend/TODO.md`에서 미완 항목 제거, 원본은 references/archived로 이전 완료

## 4. 구현 단계
1. Playwright 설치 확인 (`frontend/package.json`에 devDependency 추가)
2. `frontend/e2e/step2-integration.spec.js` 작성 — 3 시나리오
3. 에러 시나리오: MSW로 `/api/chat` 500 강제
4. `scripts/ui-regression.sh` 시나리오 번호 1–3으로 등록
5. 결과 스냅샷/보고서 PR 첨부

## 5. 위험 & 롤백
- 위험: backend 포트(8000) 점유 → worktree 포트 할당 사용
- 롤백: Playwright 도입만 되돌리면 됨(앱 코드 변경 없음)

## 6. 검증 계획
- `scripts/verify.sh`
- `scripts/ui-regression.sh --scenarios 1,2,3`
- `scripts/obs-query.py --report`

## 7. 일지
- 2026-04-17 — active 등록 (원본: backend/TODO.md)
