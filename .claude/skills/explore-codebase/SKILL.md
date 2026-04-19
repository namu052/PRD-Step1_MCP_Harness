---
name: explore-codebase
description: 새 작업 시작 시 저장소 전체 구조를 빠르게 파악한다. 읽기 전용. Write/Edit 금지.
allowed_tools: [Read, Glob, Grep, Bash]
---

# Skill: explore-codebase

## 사용 시점
- 새 작업을 시작했고, 어떤 파일이 관련되는지 불명확할 때
- 코드 수정 전에 구조·의존성·테스트 존재 여부 확인이 필요할 때

## 절차 (읽기 전용)
1. `ARCHITECTURE.md`와 `docs/policies/STRUCTURE_RULES.md`를 읽는다.
2. 과제 키워드로 `Grep`을 2–4회 수행한다. (글리프/오타 주의)
3. 후보 파일 5–15개를 `Read`로 확인한다.
4. 관련 테스트(`tests/**`, `frontend/src/**/*.test.*`)의 유무를 확인.
5. 관찰 결과를 **plan의 `## 1. Why` / `## 2. Scope`** 초안으로 작성.

## 출력
- `docs/exec-plans/active/<slug>.md`의 초안 (없으면 `_template.md` 복사)
- 관련 파일·테스트 경로 목록
- 불확실성(열린 질문) 3개 이내

## 금지
- Edit/Write/Bash(쓰기형) 호출
- 네트워크 호출
- 정책 문서 수정

## 완료 조건
- plan이 생성되었고, Scope In/Out과 열린 질문이 채워짐
