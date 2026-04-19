# CLAUDE.md — Claude Code 진입 허브

> **이 파일은 Claude Code 전용 진입점이다. 정책·지식은 모두 `docs/`에서 관리한다. 장문은 여기에 넣지 않는다.**
> 변경 시 80줄 상한을 지킨다. 상한을 초과하는 내용은 `docs/`로 옮긴다.

## 1. 먼저 읽어야 하는 문서 순서
1. `ARCHITECTURE.md`
2. `docs/policies/GOLDEN_RULES.md`
3. `docs/policies/STRUCTURE_RULES.md`
4. 해당 작업의 `docs/product-specs/` + `docs/design-docs/`
5. 활성 `docs/exec-plans/active/`
6. `docs/sops/claude-sop.md`

## 2. Claude 실행 체크리스트
- [ ] 어떤 `.claude/skills/<name>/SKILL.md`를 사용할지 확인했는가? (explore-codebase / create-exec-plan / run-verification / prepare-pr)
- [ ] `docs/exec-plans/active/`에 계획이 있는가? 없으면 `create-exec-plan` 스킬부터
- [ ] `.claude/hooks/settings.json`의 PreToolUse/PostToolUse 훅이 로컬에 활성화됐는가?
- [ ] 변경 후 `run-verification` 스킬로 `scripts/verify.sh`를 수행했는가?
- [ ] PR은 `prepare-pr` 스킬로 `.github/PULL_REQUEST_TEMPLATE.md`를 채웠는가?

## 3. 금지 사항 (세부: `docs/policies/SECURITY.md`, `docs/policies/OPERATIONS.md`)
- 비가역 명령(`rm -rf`, 강제 푸시, 강제 리셋): 사람 승인 필요
- 프로덕션 환경 변수·시크릿을 컨텍스트로 가져오지 않는다
- 거대 단일 PR 금지 — ≤ 400 LOC 권장, 초과 시 분할

## 4. 실패 시 분기
- 빌드/테스트 실패 → 원인 수정 (훅 우회 금지)
- 승인 요청 필요 → `docs/sops/human-approval-sop.md`
- 구조 위반 → `scripts/structure-check.py` 실행 후 `docs/policies/STRUCTURE_RULES.md` 준수

## 5. Claude 고유 규칙 (세부: `docs/sops/claude-sop.md`)
- **절차**는 `skills/`에, **강제**는 `hooks/`에 둔다. CLAUDE.md에 절차 본문을 복사하지 않는다.
- Agent 도구(subagent)는 대규모 탐색·독립 검토용. 남발 금지.
- 메모리(`memory/`)에는 *과제 상태*가 아닌 *사용자/프로젝트 지속 정보*만 저장.
- UI 변경은 dev server를 띄워 실제로 클릭 후 PR에 스크린샷/메모 첨부.

## 6. 끝나기 전
- `scripts/verify.sh`
- 해당 plan을 `docs/exec-plans/completed/`로 이동
- PR 설명에 DoD 체크 + 관측 지표(로그/메트릭) 확인 결과 첨부
