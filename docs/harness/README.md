# Harness — 공용 하네스 산출물 카탈로그

> **하나의 공용 코어, 두 개의 얇은 어댑터.** 이 디렉터리는 하네스 자체에 대한 설계 문서를 모은다.

## 섹션 1 — 정의
- [`definition.md`](./definition.md)

## 섹션 2 — 아키텍처
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`./core-principles.md`](./core-principles.md) *(섹션 4)*

## 섹션 3 — 리포지터리 구조
- 실제 구조는 `../../docs/generated/doc-map.md` (스크립트 생성)
- 규약: 이 파일 하단 표 참조

## 섹션 5 — 허브 파일
- [`../../AGENTS.md`](../../AGENTS.md)
- [`../../CLAUDE.md`](../../CLAUDE.md)

## 섹션 6 — 기록 시스템
- [`../design-docs/index.md`](../design-docs/index.md)
- [`../product-specs/index.md`](../product-specs/index.md)
- [`../exec-plans/active/_template.md`](../exec-plans/active/_template.md)
- [`../exec-plans/completed/_template.md`](../exec-plans/completed/_template.md)
- [`../exec-plans/tech-debt-tracker.md`](../exec-plans/tech-debt-tracker.md)

## 섹션 7 — 실행 루프 & 자율성
- [`./execution-loop.md`](./execution-loop.md)
- [`./autonomy-levels.md`](./autonomy-levels.md)

## 섹션 8 — 검증
- `../../scripts/verify.sh`, `structure-check.py`, `check-docs-freshness.py`, `check-generated-integrity.py`
- `../../.github/workflows/verify.yml`

## 섹션 9 — 구조 규칙
- [`../policies/STRUCTURE_RULES.md`](../policies/STRUCTURE_RULES.md)

## 섹션 10 — Codex 어댑터
- `../../.codex/config.toml`, `profiles/*.toml`, `config.local.example.toml`
- [`../sops/codex-sop.md`](../sops/codex-sop.md)

## 섹션 11 — Claude 어댑터
- `../../.claude/skills/{explore-codebase,create-exec-plan,run-verification,prepare-pr}/SKILL.md`
- `../../.claude/hooks/settings.json`
- [`../sops/claude-sop.md`](../sops/claude-sop.md)

## 섹션 12 — 관측/UI 검증
- [`./observability.md`](./observability.md)
- `../../observability/README.md`

## 섹션 13 — PR/리뷰/병합
- [`../policies/PR_REVIEW.md`](../policies/PR_REVIEW.md)
- [`../sops/pr-review-sop.md`](../sops/pr-review-sop.md)
- `../../.github/PULL_REQUEST_TEMPLATE.md`

## 섹션 14 — 드리프트/엔트로피
- [`../policies/DRIFT_CONTROL.md`](../policies/DRIFT_CONTROL.md)
- [`../policies/GOLDEN_RULES.md`](../policies/GOLDEN_RULES.md)
- `../../.github/workflows/drift-scan.yml`

## 섹션 15 — 운영 정책
- [`../policies/OPERATIONS.md`](../policies/OPERATIONS.md)
- [`../policies/SECURITY.md`](../policies/SECURITY.md)
- [`../policies/RELIABILITY.md`](../policies/RELIABILITY.md)
- [`../policies/QUALITY_SCORE.md`](../policies/QUALITY_SCORE.md)

## 섹션 16 — 12주 로드맵
- [`./roadmap-12-weeks.md`](./roadmap-12-weeks.md)

## 섹션 17 — 실패 패턴
- [`./failure-patterns.md`](./failure-patterns.md)

## 섹션 18 — SOP 묶음
- [`../sops/common-agent-sop.md`](../sops/common-agent-sop.md)
- [`../sops/codex-sop.md`](../sops/codex-sop.md)
- [`../sops/claude-sop.md`](../sops/claude-sop.md)
- [`../sops/human-approval-sop.md`](../sops/human-approval-sop.md)
- [`../sops/worktree-sop.md`](../sops/worktree-sop.md)
- [`../sops/pr-review-sop.md`](../sops/pr-review-sop.md)

---

## 즉시 실행 가능한 MVP (이번 주에 머지할 수 있는 최소 묶음)
1. `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md` — 슬림 허브 + 구조 계약
2. `docs/product-specs/overview.md`, `docs/policies/{GOLDEN_RULES,STRUCTURE_RULES,SECURITY}.md`
3. `scripts/verify.sh` + `structure-check.py` + `check-docs-freshness.py` + `audit-log.py`
4. `.github/workflows/verify.yml`
5. `.codex/config.toml` + `profiles/base.toml`, `.codex/config.local.example.toml`
6. `.claude/skills/{explore-codebase,create-exec-plan,run-verification,prepare-pr}` + `.claude/hooks/settings.json`
7. `.github/PULL_REQUEST_TEMPLATE.md`
8. `docs/exec-plans/active/_template.md`, `tech-debt-tracker.md`
9. `.gitignore` 갱신 (로컬 설정·worktree·generated 격리)

## 확장 버전 (4–12주차)
- 구조 검사 `tests/structure/` 정식 구현 (Python + JS 양측)
- UI 회귀 `scripts/ui-regression.sh` + Playwright 시나리오 10개
- 관측성 확장: OpenTelemetry 수집, `scripts/obs-query.py` 실데이터
- 품질 점수 자동 PR 라벨링 + 주간 대시보드 (`docs/generated/quality/score.md`)
- 드리프트 스캔 고도화 (`scripts/drift-scan.py`), cleanup 자동 PR
- 자율성 L3 cleanup-only 자동 머지 파이프라인
- design-docs 샘플 3건 작성, product-specs 주요 기능 분리 2건 추가
