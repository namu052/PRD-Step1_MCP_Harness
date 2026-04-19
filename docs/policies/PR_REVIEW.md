# PR_REVIEW — PR/리뷰/병합 체계 (섹션 13)

## 원칙
1. **작은 PR 우선** — ≤ 400 LOC 권장. 초과는 분할 유도.
2. **자기 리뷰 필수** — 에이전트가 diff를 읽고 코멘트로 자답한다.
3. **다른 에이전트 리뷰 허용** — 2차 리뷰용으로 code-reviewer 서브에이전트 사용 가능. 단, 최종 승인은 사람.
4. **사람 리뷰 필수** 케이스 — 스키마/마이그레이션, 보안, CI·정책 변경, 프로덕션 영향.
5. **실패 빌드 자동 복구** — Level 2+는 동일 실패 1회 한정 자동 재시도. 재시도도 실패 시 사람.
6. **병합 게이트** — `scripts/verify.sh` + 구조 검사 + UI 회귀 + 품질점수 ≥ 0.6.
7. **검토 가능한 변경의 정의** — (a) 단일 목적, (b) 범위 선언(In/Out), (c) DoD가 측정 가능, (d) 테스트 포함.

## PR 생성 프롬프트 템플릿
```
[PR] <type>(<scope>): <한 줄 요지>

## Summary
- ...
## Scope
- In: ...
- Out: ...
## Plan link
- docs/exec-plans/active/<slug>.md
## Verification
- [ ] scripts/verify.sh
- [ ] UI scenarios: #..
- [ ] Structure check
## Risk & Rollback
- ...
## Screenshots / logs
- ...
```

## 리뷰 프롬프트 템플릿
```
당신은 이 저장소의 code-reviewer 에이전트다. 다음 기준으로 PR #<n>을 검토하라.
1) docs/policies/GOLDEN_RULES.md 및 STRUCTURE_RULES.md 위반 여부
2) 테스트 커버리지 증가 여부
3) 관측 가능성 누락 여부
4) PR 크기/분할 여지
5) 금지 명령·시크릿 노출 여부
결과는 markdown 체크리스트 + 수정 제안 코멘트로 작성.
```

## 수정 반영 프롬프트 템플릿
```
리뷰어 코멘트 N개를 반영한다. 원칙:
- force-push 금지, 새 커밋으로 누적
- 코멘트 ID를 커밋 메시지에 포함
- 반영 후 scripts/verify.sh 재실행
- 변경 요약을 PR 설명 하단 "Review response" 절에 append
```

## 병합 승인 체크리스트
- [ ] CI green, 품질점수 ≥ 0.6
- [ ] plan의 DoD 전부 체크
- [ ] 관련 product-specs/design-docs 갱신
- [ ] 금지 항목(시크릿·절대경로) 0건
- [ ] 롤백 방법 PR 하단 명시
- [ ] 고위험이면 사람 승인자 서명(코멘트 또는 reviewers)
