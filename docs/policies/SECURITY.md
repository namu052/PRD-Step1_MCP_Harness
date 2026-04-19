# SECURITY — 보안 정책

## 원칙
- 비밀은 코드·공용 설정·메모리에 두지 않는다.
- 사용자 입력은 **경계**에서 검증하고 내부는 신뢰한다(과검증 금지).
- 데이터 접근은 역할 기반, 프로덕션 권한은 사람 승인.

## 시크릿 처리
| 위치 | 허용 여부 | 근거 |
|------|-----------|------|
| 코드 | ❌ | — |
| 공용 설정 (`.codex/config.toml`) | ❌ | `.codex/config.local.toml`로 분리 |
| 개인 `.env` | ✅ | gitignore 필수 |
| CI secrets | ✅ | GitHub Actions encrypted |
| 에이전트 컨텍스트 | ❌ | 마스킹 필수, 원문 보관 금지 |

## 위험 명령 통제
- `rm -rf`, `git push --force`, `git reset --hard`, DB `DROP`, 마이그레이션 rollback, 프로덕션 배포 → **사람 승인 전까지 차단**.
- 강제 방식:
  - Codex: `.codex/config.toml`의 `approval_policy`와 sandbox, 승인 요청 템플릿은 `docs/sops/human-approval-sop.md`.
  - Claude: `.claude/hooks/settings.json`의 PreToolUse 훅으로 명령 패턴 차단.
- 우회(`--no-verify`, `-f`, `|| true`) 사용 시 CI가 차단.

## 데이터 접근
- 개발 환경은 **합성 데이터** 우선. 실제 개인정보는 금지.
- 프로덕션 DB 연결은 사람 세션에서만. 에이전트는 **읽기 전용 replica** + 마스킹 뷰만.

## 인증/세션
- GPKI 인증 흐름은 프론트 한 곳(`components/auth/**`)에서만. 쿠키/스토리지 접근은 store를 경유.
- 세션 스토리지 키는 `docs/design-docs/`에 정의. 임의 키 금지.

## 감사 로그
- 에이전트가 실행한 Bash/Edit/승인 요청은 `observability/agent-actions/*.jsonl`에 append-only 로깅.
- 고위험 명령은 별도 stream `agent-actions/high-risk/*`에 기록.

## 위반 시 조치
| 수준 | 조치 |
|------|------|
| low | 경고 comment, tech-debt 등록 |
| med | CI 실패, 수정 후 재PR |
| high | PR 차단, Level 강등 검토 |
| critical | 즉시 merge 되돌림, 사고 리포트 |

## Codex 추가
- MCP 서버 env_vars에 시크릿 이름만, 값은 개인 shell에서.
- `allowed_commands` 화이트리스트 유지, wildcard 금지.

## Claude 추가
- hooks로 `rm -rf`, `sudo`, 프로덕션 엔드포인트 URL 포함 명령을 PreToolUse 차단.
- memory 저장 시 PII/토큰 탐지 룰 적용.
