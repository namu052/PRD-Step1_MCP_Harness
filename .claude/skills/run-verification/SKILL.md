---
name: run-verification
description: scripts/verify.sh와 구조/UI 검사를 실행하고 결과를 요약한다. 실패 시 원인 진단.
allowed_tools: [Read, Glob, Grep, Bash]
---

# Skill: run-verification

## 사용 시점
- 코드 변경 후 PR 생성 전
- CI 실패 재현/디버깅

## 절차
1. `scripts/verify.sh --quick` 실행. 통과 시 `scripts/verify.sh` 전체 실행.
2. 실패 시, 가장 먼저 실패한 검사 이름을 식별하고 로그 마지막 50줄을 추출.
3. 실패 카테고리별 대응:
   - lint → 자동 수정 시도 후 재실행(Write/Edit는 다른 스킬에서 수행)
   - typecheck → 실제 타입 오류인지, 잘못된 import인지 구별해 보고
   - unit/integration → 가장 작은 reproducer 명령을 PR에 남김
   - structure → `docs/policies/STRUCTURE_RULES.md`의 해당 항목 링크
   - UI regression → `observability/ui-snapshots/<date>/` 의 diff 이미지 위치 보고
4. 관측 지표 스냅샷 첨부: `scripts/obs-query.py --report` 실행 결과.

## 출력
- PR 코멘트 초안(성공/실패 + 실패 상세 + 재현 명령)
- plan의 `## 7. 일지`에 실행 시간·결과 append

## 금지
- `--no-verify`, `-f`, `|| true` 등 우회
- 실패를 숨기고 머지 요청

## 완료 조건
- verify.sh 전체가 통과
- 관측 리포트가 PR 코멘트에 포함
