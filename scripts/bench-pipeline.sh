#!/usr/bin/env bash
# bench-pipeline.sh — 골든셋 N회 실행 후 baseline 리포트 생성
#
# 사용:
#   scripts/bench-pipeline.sh --n 3 --report
#   scripts/bench-pipeline.sh --n 1           (리포트는 기본 생성)
#   scripts/bench-pipeline.sh --help
#
# 산출:
#   observability/metrics/pipeline.jsonl   (append)
#   observability/metrics/quality.jsonl    (append)
#   observability/reports/YYYY-MM-DD-baseline.md
#
# 전제: `.env`에 OPENAI_API_KEY, OLTA 로그인 상태(GPKI 인증서) — 없으면
#       파이프라인이 "로그인 필요" 메시지를 반환하고 타이밍 기록만 남는다.
#       실제 품질 지표 수치가 필요하면 인증서 세션이 있는 환경에서 실행한다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
GOLDEN="${BACKEND_DIR}/tests/quality/golden_questions.yaml"
REPORTS_DIR="${REPO_ROOT}/observability/reports"
DATE_TAG="$(date -u +%Y-%m-%d)"
REPORT_PATH="${REPORTS_DIR}/${DATE_TAG}-baseline.md"

N=1
GEN_REPORT=1

print_help() {
  sed -n '2,20p' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --n)       N="$2"; shift 2 ;;
    --n=*)     N="${1#*=}"; shift ;;
    --no-report) GEN_REPORT=0; shift ;;
    --report)  GEN_REPORT=1; shift ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "${GOLDEN}" ]]; then
  echo "golden set not found: ${GOLDEN}" >&2
  exit 1
fi

mkdir -p "${REPO_ROOT}/observability/metrics" "${REPORTS_DIR}"

echo "[bench] golden_set=${GOLDEN}"
echo "[bench] repeats=${N}"
echo "[bench] report=${REPORT_PATH}"

export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
export OBS_METRICS_ROOT="${REPO_ROOT}/observability/metrics"
export BENCH_N="${N}"

cd "${BACKEND_DIR}"

python - <<'PY'
import asyncio
import os
import sys
import traceback
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML 미설치: pip install pyyaml", file=sys.stderr)
    sys.exit(3)

REPO = Path(os.environ["OBS_METRICS_ROOT"]).resolve().parent.parent
GOLDEN = REPO / "backend" / "tests" / "quality" / "golden_questions.yaml"
N = int(os.environ.get("BENCH_N", "1"))

# mcp_server 전체 import 는 MCP stdio 초기화로 이어질 수 있으니,
# 파이프라인 함수만 직접 import 한다.
sys.path.insert(0, str(REPO / "backend"))
from mcp_server import _run_full_pipeline  # noqa: E402

data = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
questions = data.get("questions", [])
print(f"[bench-py] questions={len(questions)} repeats={N}")

async def run_once(q: dict, attempt: int) -> None:
    qid = q.get("id")
    try:
        await _run_full_pipeline(
            q["question"],
            skip_verification=False,
            golden_set_id=qid,
        )
        print(f"  [{qid}] attempt={attempt} ok")
    except Exception as exc:  # noqa: BLE001
        print(f"  [{qid}] attempt={attempt} FAILED: {exc}")
        traceback.print_exc(limit=2)

async def main() -> None:
    for attempt in range(1, N + 1):
        print(f"[bench-py] pass {attempt}/{N}")
        for q in questions:
            await run_once(q, attempt)

asyncio.run(main())
PY

echo "[bench] python run done"

if [[ "${GEN_REPORT}" == "1" ]]; then
  echo "[bench] generating report..."
  python "${REPO_ROOT}/scripts/obs-query.py" --report baseline --since 24h --out "${REPORT_PATH}" || {
    echo "[bench] report generation failed" >&2
    exit 4
  }
  echo "[bench] report written: ${REPORT_PATH}"
fi

echo "[bench] done"
