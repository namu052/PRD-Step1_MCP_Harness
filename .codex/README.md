# .codex/ — Codex CLI 어댑터

- `config.toml`: 공용 기본값 (PR/사람 승인 대상)
- `profiles/{base,conservative,semi-autonomous}.toml`: 위험도별 프로파일
- `config.local.example.toml` → 복사해 `config.local.toml`로 개인 설정 사용(gitignore)

정책: `docs/sops/codex-sop.md`, `docs/policies/OPERATIONS.md#op-5-위험-명령-실행-제한`.
