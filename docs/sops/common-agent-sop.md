# SOP — 공용 에이전트 실행 절차

모든 에이전트(Codex/Claude)는 본 SOP를 *먼저* 따르고, 이후 각자 SOP를 따른다.

## 1. 진입
- `ARCHITECTURE.md` → `docs/policies/GOLDEN_RULES.md` → `docs/policies/STRUCTURE_RULES.md` 순으로 읽는다.
- 과제에 해당하는 `docs/product-specs/`와 `docs/design-docs/`를 확인한다.

## 2. 계획
- `docs/exec-plans/active/`에 plan이 없으면 `_template.md`를 복사해 생성.
- 범위가 큰 경우 design-docs 후보 파일도 함께 추가.

## 3. 구현
- 작은 단위 커밋. 파일 크기 800줄/함수 50줄/중첩 4단계 유지.
- 새 헬퍼는 공용 모듈에 추가. ad-hoc 파일 생성 금지.

## 4. 검증
- `scripts/verify.sh --quick` 자주, 최종 `scripts/verify.sh`.
- UI 변경이 있으면 `scripts/ui-regression.sh` 실행.

## 5. 관측
- `scripts/obs-query.py`로 해당 경로의 메트릭/트레이스 확인.

## 6. PR
- `.github/PULL_REQUEST_TEMPLATE.md` 채움.
- 품질점수 ≥ 0.6 확인.

## 7. 정리
- `active/<slug>.md` → `completed/<slug>.md`로 이동.
- 임시 worktree·앱은 `scripts/worktree-down.sh`로 종료.
