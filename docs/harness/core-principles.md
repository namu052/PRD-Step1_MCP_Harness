# [섹션 4] 공용 코어 설계 원칙

## A. 무엇을 어디에 두는가

### 공용 코어에 둘 것 (모든 에이전트가 공유)
- `ARCHITECTURE.md`, `docs/{design-docs,product-specs,exec-plans,references,generated,harness,policies,sops}`
- `scripts/verify.sh`, `scripts/lint.sh`, `scripts/typecheck.sh`, `scripts/structure-check.py`, `scripts/check-docs-freshness.py`
- `tests/structure/` (아키텍처 규칙을 코드로)
- `observability/` (로그·메트릭·트레이스 수집 지점)
- `.github/workflows/verify.yml`, `.github/PULL_REQUEST_TEMPLATE.md`
- 정책·SOP 전부

### Codex 전용
- `AGENTS.md` (슬림 허브)
- `.codex/config.toml` (공용 부분만), `.codex/config.local.toml` (개인·MCP wiring, gitignore)
- `docs/sops/codex-sop.md`

### Claude 전용
- `CLAUDE.md` (슬림 허브)
- `.claude/skills/**`, `.claude/hooks/**`
- `docs/sops/claude-sop.md`

### 공용처럼 보이지만 실제로 분리해야 하는 것
- **승인 정책의 실체 설정값**: 철학은 공용(`docs/policies/OPERATIONS.md`), 구체 설정은 도구별(`.codex/config.toml`의 `approval_policy`, `.claude/hooks/settings.json`의 PreToolUse).
- **MCP 서버 목록**: 공유 가능한 서버는 `docs/references/`에 이름과 용도만. 실제 명령·경로는 개인 설정.
- **비밀/절대경로**: 코어에 절대 금지. 개인 파일 또는 CI secrets에만.

### 중복 관리를 막는 방법
- 정책 본문은 **`docs/policies/` 한 곳**에만 쓰고, 허브 파일(AGENTS/CLAUDE)은 링크만.
- 스크립트는 **`scripts/` 한 곳**에만 쓰고, CI·pre-commit·스킬·훅은 모두 이 스크립트를 호출.
- 드리프트 감지: `scripts/check-docs-freshness.py`가 허브 파일 줄 수 상한과 중복 섹션을 검사.

## B. 공용 코어 설계 원칙 10개
1. **Source of truth는 하나다.** 같은 규칙을 두 곳에 쓰지 않는다.
2. **권고는 자동 검사로 바꾼다.** 규칙은 lint/test/CI로 실패할 수 있어야 한다.
3. **공용 허브는 짧다.** AGENTS.md, CLAUDE.md 각 80줄 상한.
4. **도구별 차이는 어댑터로 격리한다.** 공용 코어에 도구 이름이 등장하지 않도록.
5. **스크립트 한 번, 호출은 여러 번.** 같은 검사를 여러 경로(CI, pre-commit, 스킬)에서 재구현하지 않는다.
6. **자동 생성물은 수기 편집 금지.** `docs/generated/`는 스크립트만 쓴다.
7. **계획 없는 변경 금지.** `docs/exec-plans/active/`에 plan이 있어야 코드 변경.
8. **비가역은 사람에게.** `rm -rf`, `--force`, 프로덕션 배포는 사람 승인.
9. **드리프트는 조기에 탐지한다.** 주간 점검 job이 정책·문서·코드의 불일치를 보고.
10. **실패한 에이전트 작업은 학습 대상이다.** 실패 패턴은 `docs/harness/failure-patterns.md`에 누적.

## C. Source of truth 계층
```
1. 법·제도·외부 API 스펙     ← 외부, 변경 불가, docs/references/로 포인터만
2. docs/product-specs/       ← 제품 동작 진실
3. docs/design-docs/         ← 설계 결정 진실
4. docs/policies/            ← 운영 규칙 진실 (자동 검사와 연결)
5. ARCHITECTURE.md            ← 구조 계약 진실
6. scripts/* + tests/*        ← 실행 가능한 진실 (가장 강한 계층)
7. 코드                       ← 최종 구현
```
규칙: 상위 계층이 하위 계층을 이긴다. 충돌 시 상위를 수정하고 하위를 재생성한다.

## D. 공용 문서와 도구별 파일의 관계
- AGENTS.md / CLAUDE.md는 **`docs/`를 읽는 순서와 체크리스트만** 담는다.
- `.codex/*` / `.claude/*`는 **공용 스크립트를 호출**할 뿐 자체 로직을 복제하지 않는다.
- 스킬/훅이 비대해지면 해당 로직을 `scripts/`로 빼고 스킬/훅은 얇은 래퍼로 만든다.

## E. 변경 책임 분배
| 대상 | 제안 | 검토 | 승인 |
|------|------|------|------|
| `docs/policies/**` | 에이전트 or 사람 | 사람 + 다른 에이전트 리뷰 | 사람 |
| `scripts/**`, `tests/structure/**` | 에이전트 or 사람 | CI + 사람 | 사람 |
| `.codex/config.toml` 공용 | Codex 운영자 | 사람 | 사람 |
| `.claude/skills|hooks/**` | Claude 운영자 | 사람 | 사람 |
| AGENTS.md / CLAUDE.md | 사람 | 사람 | 사람 |
| `docs/generated/**` | 스크립트 | CI | 자동 |
