# SOP — 인간 승인

## 언제 승인 필요한가
- 비가역 명령 실행(`rm -rf`, `--force`, DB drop/truncate)
- 프로덕션 변경(배포, 설정, DB)
- 정책·CI·보안 변경
- 자율성 레벨 변경
- 스키마/마이그레이션

## 요청 절차
1. 에이전트는 아래 템플릿을 **plan의 "승인 요청" 섹션** 또는 PR 코멘트로 제출
2. 승인자는 **코멘트로 approve/request-changes** + 본인 식별(사용자명)
3. 승인 로그는 `observability/agent-actions/high-risk/*.jsonl`에 자동 기록

## 템플릿
```
[APPROVAL REQUEST]
Title: <한 줄>
Plan: docs/exec-plans/active/<slug>.md
Change summary:
- ...
Risk level: low | med | high | critical
Blast radius: files/services/users
Rollback:
- ...
Evidence:
- logs:
- screenshots:
- verify.sh run:
```

## 승인자 역할
- 정책 적합성 확인
- 롤백 가능성 확인
- 증거 충분성 확인
- 승인 시 comment `approve: <username>` + 시간

## Rollback (OP-6)
- 릴리즈 PR이 `rollback-plan:` 섹션 없이 제출되면 CI가 차단한다.
- 롤백 명령은 `scripts/rollback.sh <release-tag>`로 단일화한다. (tag 필요 없는 경우 `--last`)
