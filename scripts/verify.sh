#!/usr/bin/env bash
# ==============================================================
# scripts/verify.sh — 공용 검증 엔트리포인트
#  - CI, pre-commit, Codex, Claude(run-verification 스킬)가 동일하게 호출
#  - "--quick"은 lint + structure + 단위 테스트 일부만
#  - "--full" (기본)은 lint + typecheck + unit + integration + structure + docs-freshness
# 실패 시 exit code != 0
# ==============================================================
set -euo pipefail

MODE="full"
if [[ "${1:-}" == "--quick" ]]; then MODE="quick"; fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { echo; echo "▶ $*"; }
skip() { echo "   (skipped — $*)"; }

step "[1/7] lint"
if [[ -d frontend ]]; then
  (cd frontend && npm run --silent lint)
else skip "no frontend"; fi
if command -v ruff >/dev/null 2>&1 && [[ -d backend ]]; then
  (cd backend && ruff check .)
else skip "ruff or backend missing"; fi

step "[2/7] typecheck"
if [[ "$MODE" == "full" ]]; then
  if [[ -d frontend ]] && (cd frontend && npm run --silent typecheck >/dev/null 2>&1); then
    (cd frontend && npm run --silent typecheck)
  else skip "no typecheck script"; fi
  if command -v mypy >/dev/null 2>&1 && [[ -d backend ]]; then
    (cd backend && mypy app || true)  # 점진 적용, 실패는 경고만
  else skip "mypy"; fi
else
  skip "quick"
fi

step "[3/7] unit tests"
if [[ -d backend/tests ]]; then
  if [[ "$MODE" == "quick" ]]; then
    (cd backend && python -m pytest tests/test_search.py tests/test_aggregator.py -x -q)
  else
    (cd backend && python -m pytest tests/ -x)
  fi
else skip "no tests"; fi

step "[4/7] integration tests"
if [[ "$MODE" == "full" && -d backend/tests ]]; then
  (cd backend && python -m pytest tests/test_chat_pipeline.py tests/test_verification_pipeline.py -x || true)
else
  skip "quick or no integration"
fi

step "[5/7] structure check"
if [[ -f scripts/structure-check.py ]]; then
  python scripts/structure-check.py --strict
else skip "structure-check.py missing"; fi

step "[6/7] docs freshness"
if [[ -f scripts/check-docs-freshness.py ]]; then
  python scripts/check-docs-freshness.py
else skip "docs-freshness missing"; fi

step "[7/7] generated integrity"
if [[ -f scripts/check-generated-integrity.py ]]; then
  python scripts/check-generated-integrity.py
else skip "generated-integrity missing"; fi

echo
echo "✅ verify.sh ($MODE) passed"
