#!/usr/bin/env python3
"""obs-prune.py — observability JSONL 로테이션 (14일 보관).

observability/metrics/*.jsonl 중 mtime이 14일을 초과한 파일을
observability/archive/YYYY-MM/ 로 이동한다.

사용:
  scripts/obs-prune.py --dry-run          # 무엇이 대상인지 출력만
  scripts/obs-prune.py                    # 실제 이동
  scripts/obs-prune.py --max-age-days 7   # TTL 오버라이드

design-doc: harness/observability.md §6 — 일 단위, 14일 보관.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

# Windows 콘솔 유니코드 출력
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "observability" / "metrics"
ARCHIVE = ROOT / "observability" / "archive"


def find_old_files(metrics_dir: Path, max_age_seconds: float) -> list[Path]:
    if not metrics_dir.exists():
        return []
    cutoff = time.time() - max_age_seconds
    out: list[Path] = []
    for path in metrics_dir.glob("*.jsonl"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            out.append(path)
    return sorted(out)


def archive_path_for(path: Path, archive_root: Path) -> Path:
    # 월별 하위 폴더로 분산(archive/YYYY-MM/)
    mtime_struct = time.gmtime(path.stat().st_mtime)
    month = time.strftime("%Y-%m", mtime_struct)
    return archive_root / month / path.name


def prune(metrics_dir: Path, archive_root: Path, max_age_seconds: float,
          dry_run: bool) -> int:
    candidates = find_old_files(metrics_dir, max_age_seconds)
    if not candidates:
        print(f"(no files older than {max_age_seconds / 86400:.0f}d in {metrics_dir})")
        return 0
    for src in candidates:
        dst = archive_path_for(src, archive_root)
        action = "WOULD MOVE" if dry_run else "MOVE"
        print(f"[{action}] {src.relative_to(ROOT)}  ->  {dst.relative_to(ROOT)}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    return len(candidates)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rotate observability JSONL files.")
    ap.add_argument("--dry-run", action="store_true", help="이동 없이 대상만 출력")
    ap.add_argument("--max-age-days", type=float, default=14.0,
                    help="이 일수보다 오래된 파일이 대상 (기본 14)")
    ap.add_argument("--metrics-dir", default=str(METRICS))
    ap.add_argument("--archive-dir", default=str(ARCHIVE))
    args = ap.parse_args()

    n = prune(
        metrics_dir=Path(args.metrics_dir),
        archive_root=Path(args.archive_dir),
        max_age_seconds=args.max_age_days * 86400.0,
        dry_run=args.dry_run,
    )
    verb = "would rotate" if args.dry_run else "rotated"
    print(f"{verb} {n} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
