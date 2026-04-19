# DRIFT_CONTROL — 드리프트·엔트로피 통제 (섹션 14)

## 1. 기본 원칙
- **공통 유틸 우선**: 새 헬퍼를 만들기 전에 검색 → 없으면 공용 모듈에 추가.
- **ad-hoc helper 금지**: `utils-<ad-hoc>.py|js` 이름은 구조 검사가 차단.
- **타입/스키마 경계 검증**: 외부/내부 경계는 Pydantic/Zod 스키마로 검증. 서비스 간 `dict` 유입 금지.
- **정기 편차 스캔**: 주간 job이 문서 mtime vs 코드 mtime, 허브 줄 수, 중복 섹션, 스킬 실행 빈도 0회를 보고.
- **품질 점수 갱신**: `scripts/quality-score.py`가 PR마다 산출, 주간 평균은 generated/quality/score.md.
- **자동 리팩터 PR**: lint/format-only, dependency bump, 자동 import 정렬은 자동 머지 가능. 그 외는 사람.

## 2. 정기 점검 Job
| Job | 주기 | 내용 | 출력 |
|-----|------|------|------|
| `docs-freshness` | 주 1회 | 문서 mtime·고아 파일·중복 섹션 | `docs/generated/drift-report.md` |
| `structure-scan` | PR마다 | STRUCTURE_RULES 검사 | PR 상태 |
| `quality-score` | PR마다 | 점수 산출 | PR label + 주간 snapshot |
| `skill-audit` | 월 1회 | `.claude/skills/` 사용 빈도·중복 | 리포트 issue |
| `config-lint` | PR마다 | 공용 config 금지 키 | CI 실패 |
| `tech-debt-lint` | PR마다 | TODO에 TD-ID 부여됐는가 | CI 실패 |

## 3. Drift 감지 규칙
- 문서 X가 90일 동안 수정되지 않았고, 참조하는 코드 경로가 수정됨 → 드리프트 후보.
- 허브(AGENTS.md/CLAUDE.md) 줄 수 > 80 → 즉시 경고.
- 동일 내용 블록이 두 곳 이상 등장 → 중복.
- 스킬 파일이 있으나 90일간 호출 0회 → 삭제 후보.
- `.codex/config.toml`에 gitignore 규칙 위반 키 등장 → 즉시 경고.

## 4. Cleanup PR 분류
| 분류 | 예시 | 자동 머지 |
|------|------|-----------|
| `cleanup:format` | Prettier/Black 전용 | ✅ |
| `cleanup:deps-bump` | patch/minor 의존성 | ✅ (lockfile 변경만) |
| `cleanup:docs` | 오타·링크 수정 | ✅ |
| `cleanup:dead-code` | 미사용 함수 제거 | ❌ (사람 리뷰) |
| `cleanup:structure` | 위반 교정 | ❌ |
| `cleanup:policy` | 정책 문구 조정 | ❌ (사람 승인) |

## 5. 기술부채 수치화
- 총 `open` TD 수, 평균 수명(일), severity 합산(critical=8, high=4, med=2, low=1).
- 주간 스냅샷이 `docs/generated/quality/score.md`에 포함.
- 임계치 초과(예: 합산 > 40) 시 `roadmap-12-weeks.md` 기준 해결 스프린트 자동 제안.
