#!/usr/bin/env bash
# worktree-up.sh <slug> — 작업 단위 worktree 생성 + 포트 할당 (MVP)
set -euo pipefail
SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then echo "usage: worktree-up.sh <slug>"; exit 1; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT/.worktrees/$SLUG"
mkdir -p "$ROOT/.worktrees"

if [[ -d "$TARGET" ]]; then
  echo "worktree already exists: $TARGET"; exit 0
fi

if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$ROOT" worktree add "$TARGET" HEAD
else
  mkdir -p "$TARGET"
  echo "(not a git repo — directory-only worktree created)"
fi

# 포트 할당 (backend 81xx, frontend 52xx)
HASH=$(printf '%s' "$SLUG" | cksum | awk '{print $1}')
BACKEND_PORT=$((8100 + HASH % 100))
FRONTEND_PORT=$((5200 + HASH % 100))
cat > "$TARGET/.env" <<EOF
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
EOF
echo "worktree up: $TARGET  ports backend=$BACKEND_PORT frontend=$FRONTEND_PORT"
