# scripts/

공용 엔트리포인트. CI/pre-commit/Codex/Claude가 모두 같은 스크립트를 호출한다.

| 스크립트 | 용도 |
|----------|------|
| `verify.sh [--quick]` | 통합 검증 (lint/typecheck/test/structure/docs) |
| `structure-check.py` | 아키텍처 규칙 검사 |
| `check-docs-freshness.py` | 허브 줄 수·문서 신선도·중복 헤딩 |
| `check-generated-integrity.py` | docs/generated/의 수기 편집 탐지 |
| `audit-log.py` | 에이전트 액션 append-only 로그 |
| `docs-map.py` | docs/ 트리 스냅샷을 docs/generated/doc-map.md로 |
| `quality-score.py` | PR 품질 점수 산출(MVP) |
| `obs-query.py` | observability 리포트(MVP) |
| `worktree-up.sh` / `worktree-down.sh` | 작업 단위 격리 환경 |
| `app-up.sh` | dev server 기동 |

## 설계 원칙
- 스크립트가 **진실의 실행 가능한 층**이다. 같은 검사를 CI/pre-commit/스킬/훅이 재구현하지 않는다.
- exit code로 PASS/FAIL을 통신. 사람 친화 메시지는 stdout.
- 외부 의존은 `requirements-dev.txt` / `frontend/package.json`에 고정.
