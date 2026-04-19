#!/usr/bin/env bash
# app-up.sh — backend + frontend dev 기동 (worktree-aware).
# .env가 있으면 BACKEND_PORT / FRONTEND_PORT를 우선 사용.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
[[ -f .env ]] && set -a && source .env && set +a

mkdir -p logs
( cd backend && nohup uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload > "$ROOT/logs/backend.log" 2>&1 & echo $! > "$ROOT/logs/backend.pid" )
( cd frontend && nohup npm run dev -- --port "$FRONTEND_PORT" > "$ROOT/logs/frontend.log" 2>&1 & echo $! > "$ROOT/logs/frontend.pid" )

echo "backend http://127.0.0.1:$BACKEND_PORT (pid $(cat logs/backend.pid))"
echo "frontend http://127.0.0.1:$FRONTEND_PORT (pid $(cat logs/frontend.pid))"
