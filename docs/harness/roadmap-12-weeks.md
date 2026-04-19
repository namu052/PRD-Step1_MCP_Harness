# [섹션 16] 12주 구축 로드맵

> 가정: Next.js + FastAPI + PostgreSQL + GitHub Actions. 팀 인원 1–3명, 에이전트 운영자 1명.

## 1주차 — 최소 기반
- **목표**: 공용 코어 뼈대, 슬림 허브 파일, `scripts/verify.sh` MVP 가동
- **산출물**: `ARCHITECTURE.md`, `docs/` 스켈레톤, `AGENTS.md`·`CLAUDE.md` 슬림 버전, `scripts/verify.sh`(lint+test 호출만)
- **완료 기준**: 로컬에서 `verify.sh` 통과, CI stub 실행
- **위험**: 기존 장문 `CLAUDE.md` 유지 유혹 → 강제로 `docs/product-specs/`로 이전
- **Codex 측**: `.codex/config.toml` base 초안, MCP wiring은 로컬 파일로 분리
- **Claude 측**: `.claude/skills/` 4개 스텁, hooks 최소(PreToolUse 차단 경로)
- **공용 측**: 뼈대 확정

## 2주차 — 정책·구조검사 착수
- **목표**: 정책 문서 초판 + 구조 검사 PoC
- **산출물**: `docs/policies/{GOLDEN_RULES,STRUCTURE_RULES,SECURITY}.md`, `tests/structure/` 3개 케이스, `scripts/structure-check.py`
- **완료 기준**: CI에 구조 검사 단계 추가. 샘플 위반이 CI에서 실패로 재현됨.
- **위험**: 규칙을 너무 많이 한 번에 강제 → 2개 도메인부터 시작
- **Codex 측**: AGENTS.md에서 정책 본문 제거, 링크만
- **Claude 측**: `run-verification` 스킬이 structure-check 호출하도록

## 3–4주차 — 공용 문서·제약 정착
- **목표**: product-specs/design-docs/ 1차 채움, tech-debt-tracker 가동
- **산출물**: 현 제품 스펙 1개, 주요 설계 결정 2개, tech-debt 5건 인벤토리
- **완료 기준**: 주간 드리프트 점검 job (`scripts/check-docs-freshness.py`)이 CI에 포함
- **위험**: 문서가 “있지만 아무도 안 읽음” → 스킬/허브에 반드시 링크하도록 강제
- **Codex 측**: exec-plan 템플릿 사용 강제
- **Claude 측**: `create-exec-plan` 스킬이 템플릿 채워주는 동작 검증
- **공용 측**: 문서 목록 자동 생성(`docs/generated/doc-map.md`)

## 5–6주차 — 검증 확장
- **목표**: typecheck·integration·UI regression을 `verify.sh`에 포함
- **산출물**: Playwright 시나리오 10개, `scripts/ui-regression.sh`, OTel 최소 수집
- **완료 기준**: PR마다 UI 스냅샷과 핵심 메트릭이 코멘트로 붙음
- **위험**: Playwright 불안정 → 재시도/격리 정책 명시
- **공용 측**: observability 1차 (`docs/harness/observability.md` 기반)

## 7–8주차 — 관측 가능성 강화
- **목표**: metrics/traces/logs 수집과 에이전트 질의 스크립트
- **산출물**: `scripts/obs-query.py`, `docs/generated/metrics/weekly.md` 자동화
- **완료 기준**: 에이전트가 `obs-query.py`만으로 평균/95p/트레이스 확인 가능
- **위험**: 데이터량 폭증 → 보존기간·샘플링 정책
- **공용 측**: SECURITY·RELIABILITY 정책 최종화

## 9–10주차 — 자율성 상향 실험 (Level 2 → 2.5)
- **목표**: cleanup류 Level 3 자동 머지(의존성 업데이트, lint 자동 수정)
- **산출물**: `.github/workflows/cleanup.yml`, cleanup PR 분류 체계
- **완료 기준**: 2주간 Level 3 자동 머지 0건의 롤백 사고
- **위험**: 오판 머지 → 첫 주는 강제 dry-run
- **Codex/Claude 측**: 승인 정책을 자동화 친화로 세분화

## 11–12주차 — 드리프트 자동화·마감
- **목표**: 드리프트 감지 job, 품질 점수 대시보드, 운영 SOP 완성
- **산출물**: `scripts/drift-scan.py`, `docs/generated/quality/score.md`, 모든 SOP 1.0 릴리즈
- **완료 기준**: 품질 점수 주간 변동 < 5%, 미해결 드리프트 < 3건
- **위험**: 지표가 행동을 왜곡 → 분기 1회 지표 리뷰 일정 확보
