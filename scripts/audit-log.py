#!/usr/bin/env python3
"""audit-log.py — 에이전트 액션 append-only 감사 로그.

사용:
  python scripts/audit-log.py --tool Edit --path src/foo.ts
PostToolUse 훅에서 호출되며, 로그는 observability/agent-actions/*.jsonl 로 쌓인다.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "observability" / "agent-actions"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SECRET_RE = [
    "api_key", "apikey", "secret", "token", "password",
]


def mask(path: str) -> str:
    low = path.lower()
    if any(x in low for x in SECRET_RE):
        return "<masked>"
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--path", default="")
    ap.add_argument("--extra", default="")
    args = ap.parse_args()

    agent = os.environ.get("AGENT_NAME", "claude")
    record = {
        "ts": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "agent": agent,
        "tool": args.tool,
        "path": mask(args.path),
        "extra": args.extra[:200],
    }
    target = LOG_DIR / f"{agent}.jsonl"
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
