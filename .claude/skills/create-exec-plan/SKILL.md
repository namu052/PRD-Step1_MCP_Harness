---
name: create-exec-plan
description: 작업 단위의 실행 계획을 작성/갱신한다. docs/exec-plans/active/에 저장.
allowed_tools: [Read, Glob, Grep, Write, Edit]
---

# Skill: create-exec-plan

## 사용 시점
- 아직 `docs/exec-plans/active/<slug>.md`가 없을 때
- 기존 plan의 Scope·DoD·위험이 변경되어 갱신이 필요할 때

## 절차
1. slug 정하기(kebab-case, 12자 이내 권장).
2. `docs/exec-plans/active/_template.md` 내용을 복사해 `<slug>.md` 생성.
3. 다음 항목을 채운다:
   - `## 1. Why`: 한 문단
   - `## 2. Scope`: In 3–7, Out 최소 2
   - `## 3. DoD`: 측정 가능한 체크박스
   - `## 4. 구현 단계`: 3–10 단계
   - `## 5. 위험 & 롤백`
   - `## 6. 검증 계획`: `scripts/verify.sh` 호출과 UI 시나리오 번호
4. 관련 `docs/design-docs/` 후보가 필요한지 판단 → 필요하면 *proposed* 문서 초안도 생성.
5. 관련 spec(`docs/product-specs/*`)이 부족하면 owner에게 지적.

## 출력
- `docs/exec-plans/active/<slug>.md`
- (선택) `docs/design-docs/NN-<slug>.md` (Status: proposed)

## 금지
- 코드 수정(다른 스킬이 담당)
- CI/정책 수정

## 완료 조건
- plan 템플릿 모든 섹션이 비어있지 않음
- Tool, Autonomy level, Related 필드가 채워짐
