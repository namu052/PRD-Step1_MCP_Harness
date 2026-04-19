# Tech Debt Tracker

> 모든 `TODO`, `XXX`, 임시 패치, 구조 위반, 우회책은 **여기에 등록된 상태로만** 잔존할 수 있다. 등록 없이 남은 것은 주간 스캔이 제거 PR을 자동 제안한다.

## 필드 정의
| 필드 | 설명 |
|------|------|
| ID | `TD-NNNN` (연속) |
| Created | YYYY-MM-DD |
| Area | `backend/*`, `frontend/*`, `infra`, `docs`, `harness` |
| Severity | low / med / high / critical |
| Impact | 사용자·운영에 미치는 영향 |
| Effort | S(≤0.5d) / M(≤2d) / L(>2d) |
| Owner | — |
| Due | YYYY-MM-DD (선택) |
| Status | open / scheduled / in-progress / resolved / wontfix |
| Ref | 파일경로:라인, PR, plan |

## 규칙
- 신규 등록 기준: 코드에 `TODO|FIXME|XXX` 추가, 임시 우회, 테스트 `skip`, 문서 `draft` 90일 경과.
- 심각도 `high` 이상: 2주 안에 `scheduled` 상태로 전환 필수.
- `resolved`는 PR 링크와 커밋 해시가 반드시 있어야 한다.
- `scripts/drift-scan.py`가 매주 자동 스캔 결과를 이 파일 하단 "Auto-detected" 섹션에 갱신한다. 사람은 그 결과를 위 표에 승격/기각한다.

## 현재 항목
| ID | Created | Area | Sev | Impact | Effort | Owner | Status | Ref |
|----|---------|------|-----|--------|--------|-------|--------|-----|
| TD-0001 | 2026-04-17 | backend | med | 운영상 무방하나 가독성·테스트성 저하 | L | backend | in-progress | `backend/mcp_server.py` 1039줄 > 800 — Plan 4 PR#1 로 `app/mcp/{schemas,sessions,pipeline_events}.py` 인프라 3종 추가(2026-04-18, 단위 37건 green). facade 분할(`mcp_server.py` ≤150줄 + `app/mcp/tools/*`)은 PR#2~3 이월; plan `active/backend-step8-mcp-modularization-progressive-sse` |
| TD-0002 | 2026-04-17 | backend | high | crawler 유지보수 난이도 매우 높음 | L | backend | in-progress | `crawler_service.py` 3537줄 > 800 — Plan 1 PR#1 로 `app/services/crawlers/{time_budget,crawl_cache}.py` 인프라 추가(2026-04-18). 본체 facade 분할(selectors/bbs/collection/)은 PR#2~5 이월; plan `active/backend-step5-crawler-concurrent-cache-refactor` |
| TD-0003 | 2026-04-17 | backend | med | 긴 함수로 분기·테스트 어려움 | M | backend | resolved | `_merge_bbs_board_records` 를 `_collect_bbs_candidates` / `_merge_with_fallbacks` / `_append_remaining` 3함수로 분해 (2026-04-18). structure-check --strict OK; plan `active/backend-step5-crawler-concurrent-cache-refactor` |
| TD-0004 | 2026-04-17 | backend | high | aggregator 대형 함수로 단위 테스트 약함 | M | backend | resolved | `aggregate` 174줄 → `_aggregate_claims/_aggregate_sources/_aggregate_slots/_combine` + `_weighted_overall/_apply_caps/_classify_tier` 분해(2026-04-18). structure-check --strict OK. 단위 테스트 `test_aggregator_tiers.py` 6건 추가; plan `active/backend-step7-verification-multiround-tiers-registry` |
| TD-0005 | 2026-04-17 | tests | low | 테스트 fixture 함수 길이 | S | backend | open | `backend/tests/conftest.py:50 force_fallback_paths` 57줄 > 50 |
| TD-0006 | 2026-04-17 | frontend | high | 레이어 위반 — 컴포넌트가 직접 fetch/axios 사용 | S | frontend | open | `frontend/src/components/auth/CertSelector.jsx` — lib/ 경유로 리팩터 |
| TD-0007 | 2026-04-17 | frontend | high | 레이어 위반 | S | frontend | open | `frontend/src/components/preview/PreviewPanel.jsx` — lib/ 경유 |
| TD-0008 | 2026-04-17 | tests | low | scratch 스크립트 정리 | S | backend | resolved | `backend/tests/scratch/README.md` 승격/삭제 판정 기록 (2026-04-18). live 후보 2건은 인증 환경 `backend/tests/integration/` 이동 대기, 탐색 유지 3건, 삭제 후보 4건은 차기 위생 PR; plan `active/backend-step9-scratch-tests-promotion` |
| TD-0009 | 2026-04-17 | harness | low | structure-check.py가 탐색 스크립트 제외 규칙 필요 | S | platform | resolved | `scripts/structure-check.py` `_is_scratch()` 추가 — `tests/scratch/` 하위는 파일/함수 크기 검사 예외 (2026-04-18); plan `active/backend-step9-scratch-tests-promotion` |

## Auto-detected (스크립트 영역 — 사람 직접 수정 금지)
<!-- scripts/drift-scan.py가 주기적으로 이 블록을 갱신한다 -->
```
(empty)
```
