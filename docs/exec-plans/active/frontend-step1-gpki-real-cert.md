# frontend-step1-gpki-real-cert — 실제 GPKI 인증서 기반 로그인·OLTA 연동 검증

**Status**: active
**Created**: 2026-04-17
**Owner**: frontend lead
**Tool**: claude (UI) + 사람 (실 인증서/비밀번호 투입)
**Autonomy level**: L1 → L2 (인증서 투입 이후)
**Related**: product-specs/overview, references/archived/frontend-todo-step1.md, policies/SECURITY.md

## 1. Why
Step 1 UI(인증서 선택 모달, 채팅·스트리밍, 프리뷰, StatusStepper)는 코드 레벨에서 완료. 그러나 원본 TODO의 대부분 unchecked 항목은 **실제 `~/GPKI/Certificate/class2` 인증서 + 실제 비밀번호**가 필요한 수동 검증이며, 이는 에이전트가 직접 수행할 수 없다. 사람-에이전트 협업 SOP를 정립한다.

## 2. Scope
### In
- `~/GPKI/Certificate/class2` 경로 및 `*_sig.cer`, `*_sig.key` 존재 전제 점검 스크립트 작성
- `vite gpkiPlugin()`의 실패 케이스(경로 없음·키 mismatch·잘못된 비밀번호) 에러 메시지 UX 점검
- 사람 주도 체크리스트: 인증서 카드 정보(CN/OU/유효기간), 로그인 성공/실패 UX, 로그아웃 후 모달 재표시
- OLTA `www.olta.re.kr` 실 로그인 1회 수동 확인(결과 스크린샷)
### Out
- 인증서 없는 환경에서의 실 연동 테스트(불가)
- GPKI SDK 교체

## 3. Definition of Done
- [ ] `scripts/check-gpki-env.sh` 추가 — 경로/파일 존재 확인, `openssl version` 출력
- [ ] gpkiPlugin 에러 경로 테스트(유닛) 3건
- [ ] `docs/sops/human-gpki-verification.md` 추가 — 사람 수행 체크리스트
- [ ] 사람이 수행한 결과를 이 plan의 일지에 append
- [ ] OLTA 로그인 스크린샷을 `observability/ui-snapshots/<date>/olta-login-ok.png`에 저장

## 4. 구현 단계
1. `scripts/check-gpki-env.sh` 작성 (존재 확인 + 경로/확장자만 리포트, 내용 읽기 금지)
2. gpkiPlugin 에러 경로 유닛 테스트(Vitest 도입 검토 또는 노드 `assert` 스크립트)
3. `docs/sops/human-gpki-verification.md` 작성 — 단계별 체크리스트, 실패 시 에이전트 재호출 방식
4. 사람 수행 세션: SOP 따라 체크리스트 실행 후 결과 캡처

## 5. 위험 & 롤백
- 위험: 인증서/비밀번호 로그 누출 → SECURITY 정책에 따라 **원문 저장 금지**, 훅에서 secret 패턴 차단 확인
- 롤백: 환경 의존 기능이라 코드 변경이 작음. 스크립트/SOP 추가만 되돌리면 됨

## 6. 검증 계획
- `scripts/check-gpki-env.sh` (CI에서는 skip)
- gpkiPlugin 에러 경로 유닛
- 사람 수행 체크리스트 결과(스크린샷+이 plan 일지)

## 7. 일지
- 2026-04-17 — active 등록. 실 인증서 미보유 환경에서는 (1)–(3) 단계까지 에이전트가 수행, (4) 인증서 보유자 세션에서 완결.
