# docs/generated/

> **이 디렉터리의 파일은 스크립트 전용이다. 사람이 직접 편집하지 않는다.**

## 생성물
| 경로 | 생성자 | 주기 |
|------|--------|------|
| `metrics/weekly.md` | `scripts/metrics-snapshot.py` | 주 1회 CI |
| `quality/score.md` | `scripts/quality-score.py` | 주 1회 CI |
| `doc-map.md` | `scripts/docs-map.py` | PR마다 |
| `drift-report.md` | `scripts/drift-scan.py` | 주 1회 CI |

사람 편집이 감지되면 `scripts/check-generated-integrity.py`가 CI에서 실패를 일으킨다.
