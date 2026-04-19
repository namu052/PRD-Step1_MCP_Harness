#!/usr/bin/env python3
"""check-generated-integrity.py — docs/generated/ 의 수기 편집 탐지.

MVP: 파일 상단 첫 200자 안에 "GENERATED" 마커가 존재해야 한다.
사람 편집이 들어가면 마커가 사라지므로 실패.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "docs" / "generated"

MARKER = "<!-- GENERATED"


def main() -> int:
    if not GEN.exists():
        print("docs/generated not present yet — ok")
        return 0
    bad: list[str] = []
    for p in GEN.rglob("*.md"):
        if p.name == "README.md":
            continue
        head = p.read_text(encoding="utf-8", errors="ignore")[:200]
        if MARKER not in head:
            bad.append(str(p.relative_to(ROOT)))
    if bad:
        print("VIOLATION generated files without marker:")
        for b in bad:
            print(" -", b)
        return 1
    print("generated-integrity: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
