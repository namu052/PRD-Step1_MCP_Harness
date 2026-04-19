#!/usr/bin/env bash
# worktree-down.sh <slug> — worktree 종료 및 정리
set -euo pipefail
SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then echo "usage: worktree-down.sh <slug>"; exit 1; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/.worktrees/$SLUG"
[[ -d "$TARGET" ]] || { echo "no worktree: $TARGET"; exit 0; }

# 아티팩트 이동
ARCH="$ROOT/observability/archive/$SLUG"
mkdir -p "$ARCH"
if [[ -d "$TARGET/logs" ]]; then cp -r "$TARGET/logs" "$ARCH/" 2>/dev/null || true; fi

if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$ROOT" worktree remove --force "$TARGET"
else
  rm -rf "$TARGET"
fi
echo "worktree down: $SLUG (artifacts → $ARCH)"
