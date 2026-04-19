# Reference — Codex ↔ MCP 연동 메모

기존 `.codex/config.toml`의 MCP 서버 등록 블록은 하네스 리팩터링 시 `.codex/config.local.toml`로 분리되었다. 이 문서는 원본 구성을 보존하기 위한 참고용이다.

## 원본 MCP 서버 구성 (로컬 전용, 버전관리 대상 아님)

```toml
[mcp_servers.local_tax_mcp]
command = "uv"
args = ["run", "--with-requirements", "requirements.txt", "python", "mcp_server.py"]
cwd = "C:\\...\\PRD-Step1_MCP\\backend"
startup_timeout_sec = 120
tool_timeout_sec = 300
env = { PLAYWRIGHT_HEADLESS = "false" }
env_vars = ["OPENAI_API_KEY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"]
```

## 운영 규칙
- 사용자 홈 경로·절대 경로·비밀키 환경변수 이름은 공용 `.codex/config.toml`에 **넣지 않는다**.
- 위 블록은 개인 PC의 `~/.codex/config.toml` 또는 `.codex/config.local.toml`에 두고 `.gitignore` 대상이다.
- MCP tool 사용 SOP는 `docs/sops/codex-sop.md`를 따른다.
