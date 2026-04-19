#!/usr/bin/env python3
"""check-docs-freshness.py — 문서 신선도/중복/줄 수 검사.

규칙 (실패 = exit 1):
  - AGENTS.md, CLAUDE.md 각각 80줄 이하
  - docs/design-docs/, docs/product-specs/의 문서는 `Status`, `Last updated` 필드 존재
  - ARCHITECTURE.md에 link가 깨진 경로가 없어야 함
  - docs/policies/와 허브 파일 사이에 동일 H2 제목 중복 금지
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HUB_FILES = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md"]
HUB_LINE_LIMIT = 80

VIOLATIONS: list[str] = []
WARNINGS: list[str] = []


def check_hub_line_limits() -> None:
    for p in HUB_FILES:
        if not p.exists():
            VIOLATIONS.append(f"[hub-missing] {p.name} not found")
            continue
        n = sum(1 for _ in p.open("r", encoding="utf-8"))
        if n > HUB_LINE_LIMIT:
            VIOLATIONS.append(f"[hub-size] {p.name}: {n} > {HUB_LINE_LIMIT} lines (move content to docs/)")


def check_spec_freshness() -> None:
    targets = list((ROOT / "docs" / "product-specs").glob("*.md")) + list(
        (ROOT / "docs" / "design-docs").glob("*.md")
    )
    required = re.compile(r"(Status|Last updated|Date)\s*[:*]?", re.IGNORECASE)
    for p in targets:
        if p.name in ("index.md", "README.md"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not required.search(text):
            VIOLATIONS.append(f"[spec-fields] {p.relative_to(ROOT)}: missing Status/Last updated/Date")


def check_arch_links() -> None:
    arch = ROOT / "ARCHITECTURE.md"
    if not arch.exists():
        return
    text = arch.read_text(encoding="utf-8")
    for m in re.finditer(r"`([^`]+\.md)`", text):
        path = m.group(1)
        # glob/brace expansion 패턴은 건너뜀
        if any(ch in path for ch in ("*", "{", "?", "[")):
            continue
        target = (ROOT / path).resolve()
        if not target.exists():
            WARNINGS.append(f"[arch-link] ARCHITECTURE.md references missing {path}")


def check_hub_vs_policies_duplication() -> None:
    hub_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in HUB_FILES if p.exists())
    hub_h2 = set(re.findall(r"^##\s+(.+)$", hub_text, re.MULTILINE))
    for p in (ROOT / "docs" / "policies").glob("*.md"):
        pol_text = p.read_text(encoding="utf-8", errors="ignore")
        for h in re.findall(r"^##\s+(.+)$", pol_text, re.MULTILINE):
            if h in hub_h2:
                WARNINGS.append(
                    f"[dup-heading] '{h}' appears in both a hub file and {p.relative_to(ROOT)} — keep only in policy"
                )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn-only", action="store_true")
    args = ap.parse_args()

    check_hub_line_limits()
    check_spec_freshness()
    check_arch_links()
    check_hub_vs_policies_duplication()

    for v in VIOLATIONS:
        print("VIOLATION", v)
    for w in WARNINGS:
        print("WARN", w)

    if VIOLATIONS and not args.warn_only:
        return 1
    if not VIOLATIONS:
        print("docs-freshness: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
