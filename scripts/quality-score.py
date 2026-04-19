#!/usr/bin/env python3
"""quality-score.py — PR 품질 점수(MVP).

현재 PR에 대해 입력(환경변수/옵션)을 받아 0–1 점수를 계산하고 stdout에 markdown으로 출력.
CI에서 PR 코멘트로 사용하기 위한 최소 구현.
"""
from __future__ import annotations
import argparse
import json
import sys

WEIGHTS = {
    "verify": 0.25,
    "tests_added_ratio": 0.15,
    "structure_violations": 0.15,
    "pr_size": 0.10,
    "self_review": 0.05,
    "docs_updated": 0.10,
    "ui_regression": 0.10,
    "obs_report": 0.10,
}


def score(inputs: dict) -> float:
    s = 0.0
    s += WEIGHTS["verify"] * (1.0 if inputs.get("verify_pass") else 0.0)
    tr = float(inputs.get("tests_added_ratio", 0) or 0)
    s += WEIGHTS["tests_added_ratio"] * (1.0 if tr >= 0.5 else tr / 0.5)
    sv = int(inputs.get("structure_violations", 0))
    s += WEIGHTS["structure_violations"] * (1.0 if sv == 0 else 0.5 if sv == 1 else 0.0)
    size = int(inputs.get("pr_size_lines", 0))
    s += WEIGHTS["pr_size"] * (1.0 if size <= 400 else 0.5 if size <= 800 else 0.0)
    s += WEIGHTS["self_review"] * (1.0 if inputs.get("self_review") else 0.0)
    s += WEIGHTS["docs_updated"] * (1.0 if inputs.get("docs_updated") else 0.0)
    s += WEIGHTS["ui_regression"] * (1.0 if inputs.get("ui_regression_pass") else 0.0)
    s += WEIGHTS["obs_report"] * (1.0 if inputs.get("obs_report_attached") else 0.0)
    return round(s, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-json", default="", help="JSON dict 입력")
    args = ap.parse_args()
    inp = json.loads(args.input_json) if args.input_json else {}
    val = score(inp)
    print(f"## Quality score: **{val}**")
    print()
    print("| item | weight | contribution |")
    print("|------|--------|---------------|")
    for k, w in WEIGHTS.items():
        print(f"| {k} | {w} | — |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
