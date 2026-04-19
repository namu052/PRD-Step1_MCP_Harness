# SOP — Claude Code

## 스킬 사용 우선순위
1. `.claude/skills/explore-codebase` — 코드 구조 파악
2. `.claude/skills/create-exec-plan` — 계획 생성/갱신
3. `.claude/skills/run-verification` — `scripts/verify.sh` + 구조/UI 검사
4. `.claude/skills/prepare-pr` — PR 템플릿 채움

스킬은 **절차**만 담는다. 검사 로직은 `scripts/`에 있고 스킬은 호출만 한다.

## Hooks 사용 원칙
- PreToolUse: 위험 명령 차단(rm -rf, sudo, prod URL, --force 등)
- PostToolUse: Edit 후 포매터 실행, 구조 검사 호출
- Stop: exec-plan 상태 업데이트, 관측 지표 snapshot

자세한 설정은 `.claude/hooks/settings.json`를 참조.

## Subagent 기준
- 독립적 리뷰, 대규모 탐색, 장시간 검증
- 금지: 정책 변경·프로덕션 결정·사용자 승인 대체

## Memory
- `user`, `feedback`, `project`, `reference` 4타입만. ephemeral 금지.
- 시크릿/PII 감지 시 저장 거부. 로그에 마스킹.

## UI 변경
- `scripts/app-up.sh` 로 dev server 기동 → 실제 UI 흐름 확인 → 스크린샷 저장.
- PR에 스크린샷과 관측 로그 링크 첨부.
