# tests/scratch/

공식 pytest 스위트가 아닌 **일회성 탐색·디버그 스크립트** 보관소.

## 규칙
- 이 폴더의 파일은 `pytest` 자동 수집 대상에서 **제외**(설정: `backend/pytest.ini` `norecursedirs`).
- `scripts/structure-check.py`도 이 폴더를 **제외**(파일 크기/함수 크기 규칙 미적용).
- `scripts/verify.sh`는 이 폴더를 테스트하지 않는다.
- 정식 승격 대상은 `backend/tests/integration/`으로 이동하고 `@pytest.mark.live` 마커 부여(OLTA 인증 세션에서만 실행).
- 삭제 기준: 90일 미수정 + 연관 플랜 없음.

## 승격/삭제 판정 (Plan 5 — 2026-04-18)
plan `backend-step9-scratch-tests-promotion` 결과:

| 파일 | 판정 | 근거 |
|------|------|------|
| `test_bbs_live.py` | **대기(live 후보)** | 승격 가능하나 인증 환경 부재로 실행·형태 검증 불가. `@pytest.mark.live` 마커 준비 완료, GPKI 세션에서 `backend/tests/integration/`로 이동 |
| `test_bbs_crawl.py` | **대기(live 후보)** | 동일 — E2E 타이밍 관측은 Plan 0 `@stage_timed` 로 대체되었으나 수동 시나리오 기록은 보존 가치 있음 |
| `test_collection_stats.py` | **유지(탐색)** | 진행도 이벤트 구조 디버깅용. `BoardCollectionStat` 스키마 변경 시 재사용 |
| `dump_bbs_dom.py`, `explore_olta_sub_boards.py`, `test_bbs_structure.py` | **유지(탐색)** | OLTA DOM·구조 점검 — 회귀 시 재실행 |
| `open_shared_olta.py`, `test_bbs_check.py`, `test_bbs_direct.py`, `test_e2e_timing.py` | **삭제 후보(차기 정리)** | 중복·대체됨. 본 PR에서는 미삭제(90일 규칙·회고 로그 가치 잔존), 차기 위생 PR에서 제거 |

## 승격 절차 (인증 환경에서)
1. `mkdir -p backend/tests/integration` + `__init__.py`
2. 대상 파일 상단에 `import pytest` + `@pytest.mark.live` 데코레이터 부여, `main()` 를 `test_*` 함수로 래핑
3. 기존 scratch 파일은 동일 내용의 thin shim으로 남기지 말고 **삭제**
4. `backend/pytest.ini` 의 `addopts = -m "not live"` 로 기본 수집 제외, `pytest -m live` 로 명시 실행
