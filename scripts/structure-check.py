#!/usr/bin/env python3
"""structure-check.py — 아키텍처 제약 자동 검사 (MVP).

docs/policies/STRUCTURE_RULES.md의 규칙들을 코드 레벨에서 검사한다.
실패가 있으면 exit 1. --strict 모드에서는 경고도 실패로 간주.

검사 항목(MVP):
  1) 파일 크기 상한 800줄
  2) 함수 크기 상한 50줄 (python, ruff의 C901와 별개로 단순 길이 체크)
  3) backend services에서 fastapi 직접 import 금지
  4) frontend components에서 fetch( / axios 직접 사용 금지
  5) 공용 설정 파일 절대경로/홈 경로 금지
  6) ad-hoc 헬퍼 이름 금지 (utils-*, helpers-*)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAX_FILE_LINES = 800
MAX_FUNC_LINES = 50

# ──────────────────────────────────────────────────────────────
# Grandfathered exemptions — 기존 위반은 `docs/exec-plans/tech-debt-tracker.md`
# 에 TD-ID 로 등록된 건에 한해 경고(WARN)로 강등. 신규 위반은 그대로 VIOLATION.
# 여기 목록을 늘리지 말 것. 해결 시 해당 항목을 이 리스트에서 제거.
# ──────────────────────────────────────────────────────────────
LEGACY_FILE_SIZE: dict[str, str] = {
    "backend/mcp_server.py": "TD-0001",
    "backend/app/services/crawler_service.py": "TD-0002",
}
LEGACY_FUNC_SIZE: set[tuple[str, str]] = {
    ("backend/tests/conftest.py", "force_fallback_paths"),  # TD-0005
}
LEGACY_LAYER_COMPONENT_NETWORK: dict[str, str] = {
    "frontend/src/components/auth/CertSelector.jsx": "TD-0006",
    "frontend/src/components/preview/PreviewPanel.jsx": "TD-0007",
}


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


VIOLATIONS: list[str] = []
WARNINGS: list[str] = []
GRANDFATHERED: list[str] = []


def _is_scratch(path: Path) -> bool:
    # backend/tests/scratch/ 하위는 일회성 탐색 스크립트 — 구조 규칙 예외
    parts = path.parts
    return "tests" in parts and "scratch" in parts


def scan_file_sizes() -> None:
    patterns = ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
    skip_dirs = {"node_modules", "__pycache__", "dist", "build", ".venv", ".worktrees"}
    for pat in patterns:
        for p in ROOT.glob(pat):
            if any(s in p.parts for s in skip_dirs):
                continue
            if _is_scratch(p):
                continue
            try:
                lines = sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if lines > MAX_FILE_LINES:
                rel = _rel(p)
                msg = f"[file-size] {rel}: {lines} > {MAX_FILE_LINES}"
                if rel in LEGACY_FILE_SIZE:
                    GRANDFATHERED.append(f"{msg} (grandfathered {LEGACY_FILE_SIZE[rel]})")
                else:
                    VIOLATIONS.append(msg)


def scan_python_function_sizes() -> None:
    func_re = re.compile(r"^(\s*)def\s+(\w+)\s*\(")
    for p in (ROOT / "backend").rglob("*.py"):
        if any(s in p.parts for s in ("__pycache__", ".venv")):
            continue
        if _is_scratch(p):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(src):
            m = func_re.match(line)
            if not m:
                continue
            indent = len(m.group(1))
            end = len(src)
            for j in range(i + 1, len(src)):
                nxt = src[j]
                if nxt.strip() == "":
                    continue
                cur_indent = len(nxt) - len(nxt.lstrip())
                if cur_indent <= indent and nxt.strip() and not nxt.lstrip().startswith("#"):
                    end = j
                    break
            length = end - i
            if length > MAX_FUNC_LINES and "# allow-long" not in line:
                rel = _rel(p)
                fn_name = m.group(2)
                msg = f"[func-size] {rel}:{i+1} {fn_name} = {length} > {MAX_FUNC_LINES}"
                if (rel, fn_name) in LEGACY_FUNC_SIZE:
                    GRANDFATHERED.append(f"{msg} (grandfathered TD-0005)")
                else:
                    VIOLATIONS.append(msg)


def scan_services_fastapi_imports() -> None:
    svc_dir = ROOT / "backend" / "app" / "services"
    if not svc_dir.exists():
        return
    for p in svc_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^\s*from\s+fastapi\b|^\s*import\s+fastapi\b", text, re.MULTILINE):
            VIOLATIONS.append(f"[layer] {p.relative_to(ROOT)}: services must not import fastapi")


def scan_components_direct_network() -> None:
    comp_dir = ROOT / "frontend" / "src" / "components"
    if not comp_dir.exists():
        return
    for p in comp_dir.rglob("*.jsx"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\bfetch\s*\(", text) or re.search(r"\baxios\b", text):
            rel = _rel(p)
            msg = f"[layer] {rel}: components must call via lib/, not fetch/axios directly"
            if rel in LEGACY_LAYER_COMPONENT_NETWORK:
                GRANDFATHERED.append(f"{msg} (grandfathered {LEGACY_LAYER_COMPONENT_NETWORK[rel]})")
            else:
                VIOLATIONS.append(msg)


def scan_config_absolute_paths() -> None:
    bad = [
        re.compile(r"^[A-Za-z]:\\\\"),
        re.compile(r"/home/|/Users/"),
    ]
    targets = [ROOT / ".codex" / "config.toml"]
    for t in targets:
        if not t.exists():
            continue
        text = t.read_text(encoding="utf-8", errors="ignore")
        for rx in bad:
            if rx.search(text):
                VIOLATIONS.append(f"[config] {t.relative_to(ROOT)}: absolute/home paths are forbidden in shared config")


def scan_adhoc_helpers() -> None:
    # 이름 패턴만 금지. 실제로 필요하면 공용 모듈로 승격.
    rx = re.compile(r"(^|/)(utils|helpers)-[\w-]+\.(py|js|ts|jsx|tsx)$")
    for p in ROOT.rglob("*"):
        if p.is_file() and rx.search(str(p.as_posix())):
            if "node_modules" in p.parts or "__pycache__" in p.parts:
                continue
            VIOLATIONS.append(f"[adhoc-helper] {p.relative_to(ROOT)}: promote to shared module instead")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--path", help="선택적 단일 경로(훅에서 사용)")
    args = ap.parse_args()

    scan_file_sizes()
    scan_python_function_sizes()
    scan_services_fastapi_imports()
    scan_components_direct_network()
    scan_config_absolute_paths()
    scan_adhoc_helpers()

    if not args.quiet:
        for g in GRANDFATHERED:
            print("GRANDFATHERED", g)
        for v in VIOLATIONS:
            print("VIOLATION", v)
        for w in WARNINGS:
            print("WARN", w)

    if VIOLATIONS or (args.strict and WARNINGS):
        return 1
    if not args.quiet:
        print("structure-check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
