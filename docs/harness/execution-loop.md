# [섹션 7] 공용 실행 루프

## A. 표준 루프 (Codex·Claude 공통)
```
1.  현재 상태 파악       ─ git status, 활성 exec-plan 확인
2.  관련 문서 탐색       ─ product-specs → design-docs → exec-plans
3.  실행 계획 작성/갱신  ─ docs/exec-plans/active/<slug>.md
4.  재현 or 재구성       ─ 버그는 재현 스크립트, 기능은 DoD
5.  코드 수정            ─ 작은 단위 커밋
6.  테스트 실행          ─ scripts/verify.sh --quick 수시, 마무리에 full
7.  앱 실행 & UI 검증    ─ dev server 기동 후 실제 흐름 클릭
8.  로그/메트릭/트레이스  ─ observability/에 정의된 지점 확인
9.  자기 리뷰            ─ PR diff 읽고 review 코멘트 자답
10. PR 준비              ─ .github/PULL_REQUEST_TEMPLATE.md 채움
11. 리뷰 반영            ─ 별도 커밋, force-push 금지
12. 병합 or 에스컬레이션 ─ merge gate 통과 or human approval
```

## B. 도구별 실행 포인트
| 단계 | Codex 수행 방식 | Claude 수행 방식 | 사람 개입 |
|------|------------------|------------------|-----------|
| 1–2 | CLI, subagent 탐색 | `.claude/skills/explore-codebase` | — |
| 3 | `docs/sops/codex-sop.md` 절차 | `.claude/skills/create-exec-plan` | plan 승인 |
| 4–5 | 로컬 편집 | Edit/Write 도구 | — |
| 6 | `scripts/verify.sh` | `.claude/skills/run-verification` | 실패 시 개입 |
| 7 | 수동 기동 (또는 `scripts/app-up.sh`) | 동일 | UI 샘플 확인 |
| 8 | `observability/` 쿼리 | 동일 | 이상 감지 시 개입 |
| 9 | self-review (모델 자기 리뷰) | self-review + review 서브에이전트 | — |
| 10 | `gh pr create` | `.claude/skills/prepare-pr` | PR 승인 |
| 11 | 리뷰 반영 커밋 | 동일 | 리뷰어 |
| 12 | CI 통과 → merge | CI 통과 → merge | 고위험/프로덕션 승인 |

## C. 자율성 레벨

### Level 1 — Shadow mode (관측·제안)
- **허용**: 읽기, 제안 작성, 드래프트 PR 생성(자동 병합 금지)
- **필수 검증**: 코드 변경 없음 → 구조 검사만
- **금지**: 파일 수정, 외부 네트워크 쓰기 호출
- **승인**: 모든 PR은 사람 머지
- **적합 도구**: Codex `approval_policy = "untrusted"`, Claude hooks로 Write/Edit 차단

### Level 2 — Supervised implementation (지도형 구현)
- **허용**: feature 범위 내 코드 수정, 테스트 작성, plan 작성/업데이트, PR 준비
- **필수 검증**: `scripts/verify.sh` 통과, DoD 충족, UI 수동 확인 메모
- **금지**: `docs/policies/**`, CI, 스키마/마이그레이션, 비밀 접근, 프로덕션 배포
- **승인**: PR 사람 머지, 고위험 변경은 사전 합의
- **적합 도구**: Codex `approval_policy = "on-request"`, Claude hooks는 금지 경로 차단

### Level 3 — Delegated (위임형, 범위 명시)
- **허용**: 사전 지정 범위의 자동 리팩터링, 드리프트 cleanup, 의존성 자동 업데이트 PR
- **필수 검증**: `scripts/verify.sh` + 구조 검사 + PR 품질 점수 임계치
- **금지**: 범위 외 변경. 금지 범위 위반 시 자동 중단
- **승인**: 자동 PR + 자동 머지는 **cleanup류**에만 허용. 나머지는 사람.
- **적합 도구**: Codex `approval_policy = "on-failure"` + worktree 격리, Claude는 스킬 화이트리스트 고정
