# AGENTS.md — Codex CLI 진입 허브

> **이 파일은 Codex CLI 전용 진입점이다. 정책·지식은 모두 `docs/`에서 관리한다. 장문은 여기에 넣지 않는다.**
> 변경 시 80줄 상한을 지킨다. 상한을 초과하는 내용은 `docs/`로 옮긴다.

## 1. 먼저 읽어야 하는 문서 순서
1. `ARCHITECTURE.md`
2. `docs/policies/GOLDEN_RULES.md`
3. `docs/policies/STRUCTURE_RULES.md`
4. 해당 작업의 `docs/product-specs/` + `docs/design-docs/`
5. 활성 `docs/exec-plans/active/`
6. `docs/sops/codex-sop.md`

## 2. Codex 실행 체크리스트
- [ ] `.codex/config.toml`의 approval/sandbox 모드를 작업 위험도에 맞게 선택했는가? (`base` / `conservative` / `semi-autonomous`)
- [ ] worktree에서 작업 중인가? (`docs/sops/worktree-sop.md`)
- [ ] `docs/exec-plans/active/`에 계획이 있는가? 없으면 **먼저 생성**한다.
- [ ] 변경 전 `scripts/verify.sh --quick` 통과를 확인했는가?
- [ ] 변경 후 `scripts/verify.sh` 전체 통과했는가?
- [ ] PR은 `.github/PULL_REQUEST_TEMPLATE.md`를 채웠는가?

## 3. 금지 사항 (세부: `docs/policies/SECURITY.md`, `docs/policies/OPERATIONS.md`)
- `rm -rf`, `git push --force`, `git reset --hard` 등 비가역 명령: 사람 승인 필요
- 프로덕션 환경 변수·시크릿 접근 금지. 필요한 경우 `docs/sops/human-approval-sop.md` 경로
- `.codex/config.toml`에 절대 경로·시크릿·사용자별 설정을 넣지 않는다. 그것은 `.codex/config.local.toml`(gitignore)로

## 4. 실패 시 분기
- 빌드/테스트 실패 → 원인 규명 후 수정. `--no-verify`, `-f` 등 우회 금지.
- 승인 요청 필요 → `docs/sops/human-approval-sop.md` 템플릿으로 사람에게 요청
- 구조 위반 감지 → `docs/policies/STRUCTURE_RULES.md` 참조 및 수정 후 재검증

## 5. Codex 고유 규칙 (세부: `docs/sops/codex-sop.md`)
- subagent는 **독립적 탐색 쿼리**와 **컨텍스트 격리**에만 사용. 남발 금지.
- MCP 서버 등록은 로컬 설정(`.codex/config.local.toml`)에. 공용 `config.toml`에 넣지 않는다.
- 승인 정책 기본값은 `on-request`이며, 고위험 작업은 `on-failure` 또는 수동 승인으로 강제한다.

## 6. 끝나기 전
- `scripts/verify.sh`
- `docs/exec-plans/active/`의 해당 plan을 `completed/`로 이동
- PR 설명에 DoD 체크 + 수동 검증 로그 첨부
