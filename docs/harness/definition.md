# [섹션 1] 공용 하네스의 정의

**공용 하네스**는 여러 AI 개발 에이전트가 *같은 저장소 위에서 같은 품질 기준으로* 동작하도록 강제하는 **공용 코어(문서·스크립트·테스트·CI·관측성)**와, 각 에이전트가 자기 진입 규칙을 기술하는 **얇은 도구별 어댑터**로 구성된다.

왜 Claude Code와 Codex CLI를 **하나의 파일로 합치지 않는가** — 두 도구는 진입 문서(AGENTS.md / CLAUDE.md), 확장 모델(Codex는 `.codex/config.toml` + subagents, Claude는 `.claude/skills/` + hooks), 승인·샌드박스 철학이 서로 다르기 때문에, 공용으로 묶을수록 한 쪽이 반드시 손해를 본다. 대신 운영 *규칙*은 하나여야 하므로 `docs/` + `scripts/` + CI를 공용으로 둔다.

**공용 코어에 반드시 있어야 하는 것**: `ARCHITECTURE.md`, `docs/` 전 계층, `scripts/verify.sh`를 포함한 공용 검증 스크립트, `tests/structure/`의 구조 검사, `.github/workflows/verify.yml` 병합 게이트, `observability/` 수집 지점, 정책(Golden/Structure/Security/Reliability/QualityScore/PR/Drift/Operations), SOP.

**도구별 어댑터에만 있어야 하는 것**: Codex는 `AGENTS.md`(허브), `.codex/config.toml`(approval/sandbox/worktree/project MCP), subagents 기준. Claude는 `CLAUDE.md`(허브), `.claude/skills/`(절차화), `.claude/hooks/`(강제).

**장점**: (1) 도구가 늘어도 공용 코어는 재사용. (2) 품질 게이트가 도구에 중립적. (3) 문서 중복이 줄고 드리프트 탐지가 가능.

**실패하기 쉬운 지점**: (1) AGENTS.md·CLAUDE.md에 같은 장문 정책을 복제해 드리프트 발생. (2) 스킬·훅·서브에이전트 난립으로 유지비 폭발. (3) 정책 문서가 있으나 *자동 강제*되지 않아 “권고”로 남음. (4) source of truth 위치가 모호해 에이전트가 잘못된 로컬 패턴을 학습.
