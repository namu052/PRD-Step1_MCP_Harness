# ARCHITECTURE — 공용 하네스 (Codex CLI + Claude Code)

> 한 줄 요약: **하나의 공용 코어, 두 개의 얇은 어댑터.**
> 본 문서는 저장소가 운영되는 방식의 최상위 계약이다. 세부는 `docs/`에 위임한다.

---

## 1. 핵심 원칙
1. 운영 지식(정책·설계·실행계획·품질기준)은 **공용 `docs/` + 공용 스크립트**가 source of truth다.
2. `AGENTS.md`/`CLAUDE.md`는 **짧은 진입 허브**. 장문 정책을 복제하지 않는다.
3. 도구별 차이는 `.codex/`와 `.claude/`로 격리한다. 공용 코어 80–90%, 어댑터 10–20%.
4. “권고”가 아니라 **자동 검사되고 실패 시 CI가 빨개지는** 규칙을 우선한다.
5. 사람은 승인·예외·고위험 변경·프로덕션 결정만 맡는다. 에이전트는 탐색·수정·검증·PR 준비를 맡는다.

## 2. 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Human reviewer / orchestrator                            │
│            (승인, 예외, 고위험 변경, 프로덕션 릴리즈 결정)                       │
└─────────────┬───────────────────────────────────────────────┬────────────────┘
              │                                               │
      approves/escalations                                approvals
              │                                               │
┌─────────────▼───────────────────────────────────────────────▼────────────────┐
│                         SHARED HARNESS CORE                                   │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ ARCHITECTURE  │  │    docs/     │  │  scripts/    │  │ observability/  │  │
│  │     .md       │  │ design-docs  │  │ verify.sh    │  │ logs / traces   │  │
│  │               │  │ product-specs│  │ lint.sh      │  │ metrics         │  │
│  │               │  │ exec-plans/  │  │ structure-   │  │ ui-regression   │  │
│  │               │  │ references   │  │  check.py    │  │                 │  │
│  │               │  │ generated    │  │ check-docs-  │  │                 │  │
│  │               │  │ policies/    │  │  freshness.py│  │                 │  │
│  │               │  │ sops/        │  │              │  │                 │  │
│  └───────────────┘  └──────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐   │
│  │   tests/      │  │  tooling/    │  │    CI / quality gates            │   │
│  │ structure/    │  │ (pre-commit, │  │  (.github/workflows/verify.yml)  │   │
│  │ unit/integr.  │  │  formatters) │  │  gate: verify.sh must pass       │   │
│  └───────────────┘  └──────────────┘  └──────────────────────────────────┘   │
└───────────────▲─────────────────────────────────────────────▲───────────────┘
                │                                             │
   (thin adapter)                                  (thin adapter)
                │                                             │
┌───────────────┴────────────┐                  ┌─────────────┴────────────────┐
│       CODEX ADAPTER        │                  │      CLAUDE ADAPTER          │
│  AGENTS.md (entry hub)     │                  │  CLAUDE.md (entry hub)       │
│  .codex/config.toml        │                  │  .claude/skills/             │
│    - approval policy       │                  │    explore-codebase          │
│    - sandbox mode          │                  │    create-exec-plan          │
│    - worktree strategy     │                  │    run-verification          │
│    - project MCP wiring    │                  │    prepare-pr                │
│  .codex/config.local.toml  │                  │  .claude/hooks/settings.json │
│    (개인/로컬, gitignore)    │                  │    PreToolUse / PostToolUse │
└────────────┬───────────────┘                  └──────────────┬───────────────┘
             │                                                 │
             └────────────────────┬────────────────────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │ PR review loop →        │
                     │ merge gate →            │
                     │ cleanup / drift jobs    │
                     └─────────────────────────┘
```

## 3. 각 요소 역할 요약

| 요소 | 역할 | 입력 | 출력 |
|------|------|------|------|
| Human reviewer | 승인·에스컬레이션·고위험 결정 | PR, 실패 리포트 | approve / request-changes / escalate |
| `ARCHITECTURE.md` | 구조·계약 정의 | 개발자/에이전트 | 읽을 순서와 경계 |
| `docs/design-docs/` | 기술 설계의 source of truth | 사람/에이전트 | 설계 결정 아카이브 |
| `docs/product-specs/` | 제품 동작·요구의 source of truth | PM/개발자 | 기능 스펙 |
| `docs/exec-plans/active/` | 진행 중 작업 계획 | 에이전트/사람 | 실행 단위·DoD |
| `docs/exec-plans/completed/` | 완료된 계획의 기록 | — | 회고·참조 |
| `docs/references/` | 외부/레거시 참고 | 사람 | 정적 참조 |
| `docs/generated/` | 스크립트가 생성 | `scripts/` | 자동 생성물, 사람이 직접 수정 금지 |
| `docs/policies/` | 보안·신뢰성·구조·PR 정책 | 사람 | CI 게이트와 링크된 규칙 |
| `docs/sops/` | 표준 운영 절차 | 사람/에이전트 | 실행 가이드 |
| `scripts/` | 공용 검증 커맨드 집합 | 에이전트/CI | exit code 로 게이트링 |
| `tests/structure/` | 아키텍처 제약 자동 검사 | 코드베이스 | PASS/FAIL |
| `observability/` | 로그·메트릭·트레이스 수집 지점 | 앱 | 분석 데이터 |
| `.github/workflows/verify.yml` | 병합 게이트 | PR | checks |
| `AGENTS.md` | Codex 진입 허브 (≤80줄) | Codex CLI | 우선 읽을 문서 순서 |
| `.codex/config.toml` | Codex 실행 정책 | Codex CLI | approval/sandbox/worktree |
| `CLAUDE.md` | Claude 진입 허브 (≤80줄) | Claude Code | 우선 읽을 문서 순서 |
| `.claude/skills/*/SKILL.md` | Claude 절차(Explore/Plan/Verify/PR) | Claude | 결과 산출 |
| `.claude/hooks/*.json` | PreToolUse/PostToolUse 강제 | Claude | 차단/자동 실행 |

## 4. 읽기 우선순위 (모든 에이전트 공통)
1. `ARCHITECTURE.md` (이 문서)
2. `docs/policies/GOLDEN_RULES.md`
3. `docs/policies/STRUCTURE_RULES.md`
4. 해당 작업과 관련된 `docs/product-specs/*`
5. 해당 작업과 관련된 `docs/design-docs/*`
6. 활성 `docs/exec-plans/active/*`
7. 도구별 SOP: `docs/sops/codex-sop.md` 또는 `docs/sops/claude-sop.md`

## 5. 변경 책임 분배
| 대상 | 변경 주체 | 비고 |
|------|----------|------|
| 공용 `docs/`, `scripts/`, `tests/structure/`, `.github/` | 사람 + 공용 에이전트 | PR 필수, 사람 리뷰 필수 |
| `.codex/config.toml` (공용 부분) | 사람 + Codex 운영자 | PR, 최소 1인 승인 |
| `.codex/config.local.toml` | 개인 | gitignore, 리뷰 대상 아님 |
| `.claude/skills/**`, `.claude/hooks/**` | 사람 + Claude 운영자 | PR, 스킬 변경은 `docs/design-docs/` 링크 필요 |
| `AGENTS.md` / `CLAUDE.md` | 사람만 | 슬림 허브 유지, 줄 수 상한 준수 |
| `docs/generated/**` | 스크립트만 | 사람 직접 편집 금지 |

## 6. 품질 게이트 (병합 조건)
1. `scripts/verify.sh` 통과 (lint, typecheck, unit, structure, docs-freshness).
2. `tests/structure/**` 통과 (아키텍처 제약).
3. `docs/exec-plans/active/*`에 해당 변경의 plan이 존재하고 DoD가 만족됨.
4. PR 크기 ≤ 400 LOC 권장, 초과 시 리뷰어가 분할 요청 가능.
5. `docs/policies/SECURITY.md` 위반 항목(시크릿, 위험 명령 등) 0건.

## 7. 관련 문서 지도
- 정의 및 원칙: `docs/harness/definition.md`, `docs/harness/core-principles.md`
- 실행 루프: `docs/harness/execution-loop.md`
- 자율성 수준: `docs/harness/autonomy-levels.md`
- 관측 가능성: `docs/harness/observability.md`
- 12주 로드맵: `docs/harness/roadmap-12-weeks.md`
- 실패 패턴: `docs/harness/failure-patterns.md`
- 정책: `docs/policies/{GOLDEN_RULES,STRUCTURE_RULES,SECURITY,RELIABILITY,QUALITY_SCORE,PR_REVIEW,DRIFT_CONTROL,OPERATIONS}.md`
- SOP: `docs/sops/{common-agent,codex,claude,human-approval,worktree,pr-review}-sop.md`
