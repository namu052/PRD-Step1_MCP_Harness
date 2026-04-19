---
name: prepare-pr
description: PR 템플릿을 채우고 품질 점수 요약을 생성한다. 자기 리뷰 수행.
allowed_tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Skill: prepare-pr

## 사용 시점
- 기능/버그 수정이 끝나고 `run-verification`이 통과한 뒤

## 절차
1. `.github/PULL_REQUEST_TEMPLATE.md` 복사 → 각 섹션 채움(`Summary/Scope/Plan link/Verification/Risk & Rollback/Screenshots`).
2. 자기 리뷰: diff를 훑고 다음 체크:
   - 금지 항목(시크릿·절대경로·`console.log`·임시 mock) 0건
   - ad-hoc 헬퍼 파일 추가 없는가
   - `TODO/FIXME`에 `TD-NNNN` ID 부여됐는가
3. 품질 점수: `scripts/quality-score.py` 실행 → 결과를 PR 하단 `## Quality score` 섹션에 첨부.
4. plan 상태 업데이트: `docs/exec-plans/active/<slug>.md`의 일지에 PR 링크 append.
5. 머지 전까지 `active/`에 두고, 머지 후 `completed/`로 이동(이 스킬의 범위 아님, `pr-review-sop` 참조).

## 출력
- PR 본문(마크다운), `gh pr create --body-file` 로 바로 사용 가능

## 금지
- 리뷰어 지정 자동화(조직 정책 따름)
- 사람 승인 우회

## 완료 조건
- 템플릿 모든 섹션 채움
- 품질 점수 ≥ 0.6
- plan 일지 업데이트
