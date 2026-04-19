# SOP — Codex CLI

## 프로파일 선택
| 작업 유형 | 프로파일 | 파일 |
|----------|---------|------|
| 탐색·리서치·리뷰 | base | `.codex/profiles/base.toml` |
| 공용 docs·정책 변경 | conservative | `.codex/profiles/conservative.toml` |
| 범위 한정 자동 작업(cleanup/dep bump) | semi-autonomous | `.codex/profiles/semi-autonomous.toml` |

`codex --profile <name>` 또는 환경변수 `CODEX_PROFILE`로 선택한다.

## 실행 체크
1. worktree에서 작업 (`scripts/worktree-up.sh <slug>`)
2. `docs/exec-plans/active/<slug>.md` 존재 확인
3. 작업 중 `scripts/verify.sh --quick`
4. 종료 시 `scripts/verify.sh`, `scripts/worktree-down.sh`

## 서브에이전트 사용 기준
- 대규모 탐색(파일 그룹 검색, 다중 레퍼런스 추출)
- 독립적 수행이 가능한 검증(격리 샌드박스에서 빌드/테스트)
- 금지: 정책·프로덕션 결정·사람 승인 대체

## 위험 명령 통제
- `.codex/config.toml`의 `allowed_commands`에 없는 명령은 `approval_policy`에 따라 승인 요청.
- 비가역 명령은 항상 사람 승인.

## 승인 요청 템플릿
```
[APPROVAL] <slug> — <command or change summary>
- Why: ...
- Impact: files/services/users
- Rollback: ...
- Evidence: logs/screenshots/plan link
```

## MCP 서버
- 공용 `.codex/config.toml`에 MCP 블록을 두지 않는다.
- 각 개발자는 `.codex/config.local.toml`에 본인용 구성을 둔다. 샘플은 `docs/references/codex-mcp-server.md`.
