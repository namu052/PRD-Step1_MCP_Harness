# observability/

| 경로 | 용도 |
|------|------|
| `agent-actions/*.jsonl` | 에이전트 Bash/Edit/Write 감사 로그 (append-only) |
| `agent-actions/high-risk/*.jsonl` | 고위험 승인 요청·결정 로그 |
| `ui-snapshots/<date>/` | Playwright 스크린샷/DOM dump |
| `archive/<slug>/` | worktree 종료 시 이동되는 아티팩트 |

## 원칙
- 에이전트는 **`scripts/obs-query.py`를 통해서만** 조회한다. 원시 파일 grep 금지.
- 보존 기간: agent-actions 90일, ui-snapshots 30일, archive 14일(파이프라인 예정).
- 로그는 구조화 JSON. 필수 필드: `ts, agent, tool, path, extra`.

## 데이터 흐름
```
Claude hook PostToolUse → scripts/audit-log.py → observability/agent-actions/<agent>.jsonl
Codex CLI audit         → observability/agent-actions/codex.jsonl
Playwright (UI)         → observability/ui-snapshots/
worktree-down.sh        → observability/archive/<slug>/
```
