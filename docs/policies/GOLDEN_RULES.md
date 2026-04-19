# GOLDEN_RULES — 어떤 에이전트도 어길 수 없는 규칙

> 이 문서의 규칙은 모두 **자동 검사와 연결**되어 있어야 한다. 검사 링크가 없으면 규칙이 아니라 권고다.

| # | 규칙 | 강제 방법 |
|---|------|-----------|
| G1 | Source of truth는 하나 — 같은 규칙은 두 곳에 쓰지 않는다 | `scripts/check-docs-freshness.py` 중복 섹션 탐지 |
| G2 | 공용 허브(AGENTS.md / CLAUDE.md)는 각 80줄 이하 | `scripts/check-docs-freshness.py` 줄 수 검사 |
| G3 | 정책 본문을 허브에 복사하지 않는다 | 위와 동일(헤딩 블랙리스트) |
| G4 | `docs/generated/`는 사람이 수정하지 않는다 | `scripts/check-generated-integrity.py` |
| G5 | 변경 전 `docs/exec-plans/active/`에 plan 존재 | PR 체크: plan 링크 없으면 실패 |
| G6 | `scripts/verify.sh` 통과 없이 머지 금지 | CI required check |
| G7 | 구조 규칙 위반 금지 | `tests/structure/**` |
| G8 | 비가역 명령(`rm -rf`, `--force`, 프로덕션 배포)은 사람 승인 | Codex approval, Claude hooks로 차단 |
| G9 | 시크릿·절대경로·사용자별 값은 공용 파일에 금지 | `scripts/lint-config.py` |
| G10 | 공용 유틸을 먼저 찾고, 없으면 추가한다(ad-hoc helper 금지) | `scripts/duplicate-helper-scan.py` |
| G11 | PR 크기는 ≤ 400 LOC 권장, 초과는 분할 검토 | CI 경고(차단은 옵션) |
| G12 | TODO/FIXME는 `tech-debt-tracker.md` ID 참조 필수 | `scripts/tech-debt-lint.py` |

## 개정
규칙 추가/삭제는 PR + 사람 승인 1인 이상. 추가 시 반드시 자동 검사와 CI 링크를 함께 제출한다.
