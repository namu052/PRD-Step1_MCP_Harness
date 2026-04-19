# SOP — Worktree 운영

> 작업 단위 독립 환경. 에이전트의 변경이 메인 체크아웃을 오염시키지 않도록.

## 원칙
- 모든 Level 2+ 작업은 worktree에서 진행.
- 각 worktree는 고유 포트/디렉터리/env 파일 접두사를 가진다.
- 종료 시 반드시 cleanup. 누수 발생 시 CI에서 경고.

## 디렉터리 규약
```
.worktrees/
  <slug>/
    backend/   # git worktree add
    frontend/  # 동일 worktree 내 서브 경로
    .env       # slug별 포트/경로
    logs/      # 실행 로그
```

## 생성
```bash
scripts/worktree-up.sh <slug>
# 내부 동작:
#  1) git worktree add .worktrees/<slug> origin/main
#  2) .env 에 BACKEND_PORT, FRONTEND_PORT 할당(기본 8100+ / 5200+)
#  3) scripts/app-up.sh 로 대기(health check)
```

## 종료
```bash
scripts/worktree-down.sh <slug>
# 내부 동작:
#  1) 앱 프로세스 stop
#  2) 임시 DB/SQLite 삭제
#  3) .worktrees/<slug> remove
#  4) observability/archive/<slug>/에 아티팩트만 이동
```

## 에이전트 규칙
- worktree 밖에서 파일 쓰기 금지(훅으로 차단).
- worktree 내 생성된 임시 파일은 종료 시 제거.
- 결과물은 PR로만 반영(각 worktree 내부에서 `git add`/`push`).

## 포트 충돌
- 포트 할당표는 `docs/generated/worktree-ports.md`에 자동 갱신.
- 충돌 시 `scripts/worktree-up.sh`가 다음 사용 가능 포트로 자동 할당.
