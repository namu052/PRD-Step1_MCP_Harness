"""Development server with hot-reload and ProactorEventLoop (Windows-safe).

Usage:
    python run_dev.py

Why this exists:
    uvicorn --reload forces WindowsSelectorEventLoopPolicy on Windows,
    which breaks Playwright's asyncio.create_subprocess_exec.  This script
    avoids the issue by running uvicorn WITHOUT --reload (so ProactorEventLoop
    is used) and implementing file-watching externally via watchfiles.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

# Ensure ProactorEventLoop policy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BACKEND_DIR = Path(__file__).parent
WATCH_DIR = BACKEND_DIR / "app"


def start_server() -> subprocess.Popen:
    """Start uvicorn WITHOUT --reload (preserves ProactorEventLoop)."""
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BACKEND_DIR),
    )


def main():
    try:
        from watchfiles import watch
    except ImportError:
        print("watchfiles not installed — running without hot-reload")
        print("Install with: pip install watchfiles")
        proc = start_server()
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return

    proc = start_server()
    print(f"[run_dev] Server started (PID {proc.pid}). Watching {WATCH_DIR} ...")

    try:
        for changes in watch(WATCH_DIR, watch_filter=None):
            changed = ", ".join(str(Path(c[1]).relative_to(BACKEND_DIR)) for c in changes)
            print(f"\n[run_dev] Changes detected: {changed}")
            print("[run_dev] Restarting server...")

            # Graceful stop
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

            time.sleep(0.3)
            proc = start_server()
            print(f"[run_dev] Server restarted (PID {proc.pid})")
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\n[run_dev] Server stopped.")


if __name__ == "__main__":
    main()
