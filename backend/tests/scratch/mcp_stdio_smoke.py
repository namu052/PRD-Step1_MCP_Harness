"""stdio smoke: initialize + tools/list.

로컬 MCP 기동 확인용. `python backend/tests/scratch/mcp_stdio_smoke.py`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[2]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.Popen(
        [sys.executable, str(BACKEND / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(BACKEND),
    )
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    for m in msgs:
        proc.stdin.write((json.dumps(m) + "\n").encode("utf-8"))
    proc.stdin.flush()
    try:
        out, _ = proc.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    responses = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            responses.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    init = next((r for r in responses if r.get("id") == 1), None)
    tlist = next((r for r in responses if r.get("id") == 2), None)
    ok_init = bool(init and "result" in init)
    tools = [t["name"] for t in (tlist or {}).get("result", {}).get("tools", [])]
    print(f"initialize ok: {ok_init}")
    print(f"tools ({len(tools)}): {tools}")
    return 0 if (ok_init and len(tools) == 9) else 1


if __name__ == "__main__":
    sys.exit(main())
