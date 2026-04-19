#!/usr/bin/env python3
"""obs-query.py — observability 로그/메트릭 조회.

지원 기능
- `--report agent-actions` : 기존 에이전트 액션 요약 (기본값 유지)
- `--metric p50|p95 --stage <name> --since <dur>` : pipeline.jsonl 퍼센타일 집계
- `--report baseline`       : 골든셋 baseline 리포트 md 생성 (stdout 또는 --out)

입력:
  observability/metrics/pipeline.jsonl  (design-doc 00 스키마)
  observability/metrics/quality.jsonl
  observability/agent-actions/*.jsonl   (기존)

사용 예:
  scripts/obs-query.py --metric p50 --stage crawling --since 24h
  scripts/obs-query.py --report baseline --out observability/reports/2026-04-18-baseline.md
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Windows cp949 콘솔에서도 유니코드 출력이 가능하도록 stdout 재설정
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "observability" / "metrics"
ACTIONS = ROOT / "observability" / "agent-actions"
PIPELINE_FILE = METRICS / "pipeline.jsonl"
QUALITY_FILE = METRICS / "quality.jsonl"

_STAGE_ORDER = [
    "search_planning",
    "crawling",
    "ranking",
    "evidence_grouping",
    "drafting",
    "verifying",
]


# ── 공용 파서 ────────────────────────────────────────────────────────────
def _parse_duration(expr: str) -> timedelta:
    """'24h', '15m', '30s', '7d' 형태 파싱."""
    if not expr:
        return timedelta(days=36500)
    m = re.fullmatch(r"(\d+)([smhd])", expr.strip())
    if not m:
        raise ValueError(f"invalid --since: {expr!r}")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(seconds=n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit])


def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _load_jsonl(path: Path, since: timedelta | None = None) -> list[dict]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - since if since else None
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cutoff is not None:
                try:
                    if _parse_iso(rec.get("ts", "")) < cutoff:
                        continue
                except ValueError:
                    continue
            out.append(rec)
    return out


# ── 퍼센타일 ──────────────────────────────────────────────────────────────
def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    k = (len(vs) - 1) * (pct / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return vs[lo]
    return vs[lo] + (vs[hi] - vs[lo]) * (k - lo)


def cmd_metric(metric: str, stage: str, since: str) -> str:
    span = _parse_duration(since)
    records = _load_jsonl(PIPELINE_FILE, since=span)
    if stage:
        records = [r for r in records if r.get("stage") == stage]
    values = [float(r.get("duration_ms", 0)) for r in records if r.get("status", "").startswith("ok") or r.get("status") == "cache_hit"]
    if not values:
        return f"(no data) stage={stage or '*'} since={since or 'all'}"
    pct_map = {"p50": 50.0, "p75": 75.0, "p90": 90.0, "p95": 95.0, "p99": 99.0}
    if metric not in pct_map:
        return f"unknown metric {metric!r}. supported: {sorted(pct_map)}"
    v = _percentile(values, pct_map[metric])
    return f"{metric} stage={stage or '*'} n={len(values)} = {v:.0f} ms"


# ── 리포트 ───────────────────────────────────────────────────────────────
def cmd_report_agent_actions() -> str:
    if not ACTIONS.exists():
        return "(no observability/agent-actions data yet)"
    counter: Counter[str] = Counter()
    total = 0
    for p in ACTIONS.glob("*.jsonl"):
        for line in p.open("r", encoding="utf-8"):
            try:
                rec = json.loads(line)
                counter[rec.get("tool", "?")] += 1
                total += 1
            except json.JSONDecodeError:
                continue
    lines = [f"## Agent actions ({total} total)"]
    for tool, n in counter.most_common():
        lines.append(f"- {tool}: {n}")
    return "\n".join(lines)


def _aggregate_by_stage(records: list[dict]) -> dict[str, dict[str, float]]:
    by_stage: dict[str, list[float]] = defaultdict(list)
    for r in records:
        stage = r.get("stage")
        if stage and r.get("status") in ("ok", "cache_hit", "timeout_fallback"):
            by_stage[stage].append(float(r.get("duration_ms", 0)))
    out: dict[str, dict[str, float]] = {}
    for stage, values in by_stage.items():
        if not values:
            continue
        out[stage] = {
            "n": float(len(values)),
            "p50": _percentile(values, 50),
            "p95": _percentile(values, 95),
            "mean": float(statistics.fmean(values)),
        }
    return out


def _aggregate_quality(records: list[dict]) -> dict[str, float | int | None]:
    def _pick(key: str) -> list[float]:
        return [float(r[key]) for r in records if r.get(key) is not None]

    citations = _pick("verified_citation_rate")
    conf = _pick("overall_confidence")
    hallu = _pick("hallucination_rate")
    coverage = _pick("coverage_score")

    tier_counter: Counter[str] = Counter()
    for r in records:
        t = r.get("confidence_tier")
        if t:
            tier_counter[t] += 1

    revision_triggered = sum(1 for r in records if r.get("revision_triggered"))

    return {
        "n": len(records),
        "verified_citation_rate_mean": statistics.fmean(citations) if citations else None,
        "overall_confidence_mean": statistics.fmean(conf) if conf else None,
        "hallucination_rate_mean": statistics.fmean(hallu) if hallu else None,
        "coverage_score_mean": statistics.fmean(coverage) if coverage else None,
        "revision_trigger_rate": (revision_triggered / len(records)) if records else None,
        "confidence_tiers": dict(tier_counter),
    }


def cmd_report_baseline(since: str, out_path: Path | None) -> str:
    span = _parse_duration(since) if since else None
    pipeline = _load_jsonl(PIPELINE_FILE, since=span)
    quality = _load_jsonl(QUALITY_FILE, since=span)

    stage_stats = _aggregate_by_stage(pipeline)
    q_stats = _aggregate_quality(quality)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append(f"# Baseline Report — {today}")
    lines.append("")
    lines.append(f"**생성 시각 (UTC)**: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"**기간 필터**: `--since {since or 'all'}`")
    lines.append(f"**소스**: `{PIPELINE_FILE.relative_to(ROOT)}`, `{QUALITY_FILE.relative_to(ROOT)}`")
    lines.append("")
    lines.append("## 1. Pipeline Stage Latency (ms)")
    lines.append("")
    if stage_stats:
        lines.append("| Stage | N | P50 | P95 | Mean |")
        lines.append("|-------|---|-----|-----|------|")
        for stage in _STAGE_ORDER:
            s = stage_stats.get(stage)
            if not s:
                continue
            lines.append(
                f"| {stage} | {int(s['n'])} | {s['p50']:.0f} | {s['p95']:.0f} | {s['mean']:.0f} |"
            )
        # 미등록 stage도 보존
        for stage, s in sorted(stage_stats.items()):
            if stage in _STAGE_ORDER:
                continue
            lines.append(
                f"| {stage} | {int(s['n'])} | {s['p50']:.0f} | {s['p95']:.0f} | {s['mean']:.0f} |"
            )
    else:
        lines.append("_(pipeline.jsonl 에 유효 기록 없음)_")
    lines.append("")
    lines.append("## 2. Quality Metrics")
    lines.append("")
    if q_stats.get("n"):
        lines.append("| 지표 | 값 |")
        lines.append("|------|----|")
        lines.append(f"| 총 응답 수 (N) | {q_stats['n']} |")
        for key in (
            "verified_citation_rate_mean",
            "overall_confidence_mean",
            "hallucination_rate_mean",
            "coverage_score_mean",
            "revision_trigger_rate",
        ):
            v = q_stats.get(key)
            if v is None:
                lines.append(f"| {key} | _null_ |")
            else:
                lines.append(f"| {key} | {v:.3f} |")
        tiers = q_stats.get("confidence_tiers") or {}
        if tiers:
            lines.append(f"| confidence_tiers | {tiers} |")
    else:
        lines.append("_(quality.jsonl 에 유효 기록 없음)_")
    lines.append("")
    lines.append("## 3. 사람이 검수할 것 (Gate A)")
    lines.append("")
    lines.append("- [ ] Stage P50 값이 체감 경험과 일치하는가")
    lines.append("- [ ] 골든셋 20문항 전수가 1회 이상 실행됐는가")
    lines.append("- [ ] 이후 Plan 1/2/3 PR 에 이 리포트를 baseline 으로 첨부했는가")
    lines.append("")

    text = "\n".join(lines) + "\n"
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return text


# ── CLI ──────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", nargs="?", const="agent-actions", default=None,
                    help="agent-actions | baseline")
    ap.add_argument("--metric", default="", help="p50 | p75 | p90 | p95 | p99")
    ap.add_argument("--stage", default="", help="pipeline stage 이름 (빈 값 = 전체)")
    ap.add_argument("--since", default="", help="e.g. 24h, 1h, 7d")
    ap.add_argument("--out", default="", help="(baseline 리포트) 저장 경로")
    ap.add_argument("--trace", default="", help="(stub) req_id 단위 추적")
    args = ap.parse_args()

    if args.metric:
        print(cmd_metric(args.metric, args.stage, args.since))
        return 0
    if args.report == "baseline":
        out_path = Path(args.out) if args.out else None
        print(cmd_report_baseline(args.since, out_path), end="")
        return 0
    if args.trace:
        recs = [r for r in _load_jsonl(PIPELINE_FILE) if r.get("req_id") == args.trace]
        if not recs:
            print(f"(no records for req_id={args.trace})")
            return 0
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        return 0

    # 기본값: 기존 agent-actions 요약 (하위 호환)
    print(cmd_report_agent_actions())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
