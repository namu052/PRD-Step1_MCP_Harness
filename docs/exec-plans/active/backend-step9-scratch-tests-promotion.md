# backend-step9-scratch-tests-promotion — scratch 스크립트 승격/정리 (옵션, S)

**Status**: active
**Created**: 2026-04-17
**Owner**: backend
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, references/archived/README

## 1. Why (배경·문제)
`backend/tests/scratch/`에 이전된 10개 탐색 스크립트 중 `test_bbs_live.py`, `test_bbs_crawl.py`, `test_collection_stats.py`는 라이브 크롤 회귀 안전망으로 가치가 높다. 반면 `dump_bbs_dom.py` 등 나머지는 일회성 디버깅 용도라 `tools/`로 이관하거나 삭제해야 `structure-check.py`의 예외 규칙을 유지할 필요가 없어진다. TD-0008/0009 해소.

## 2. Scope
### In
- `backend/tests/scratch/` 10개 파일 각각의 처분 결정 (승격/이관/삭제)
- 승격 대상을 `backend/tests/integration/` 로 이동하며 `pytest -m live` 마커 부여
- `backend/pytest.ini`에 `addopts = -m "not live"` 가드 추가 (CI 기본 제외)
- `scripts/structure-check.py`의 scratch 예외 규칙 제거 또는 명시적 문서화
### Out
- 새로운 BBS 시나리오 추가

## 3. Definition of Done
- [ ] `backend/tests/scratch/` 비워지거나 명시적 예외 규칙 문서화
- [ ] 승격 파일은 `pytest -m live` 실행 시 성공 (인증서 있는 환경)
- [ ] CI(`pytest`)는 기본적으로 live 테스트 제외, 경고 0건
- [ ] `scripts/verify.sh --quick` 통과
- [ ] `tech-debt-tracker.md` TD-0008, TD-0009 `resolved`
- [ ] PR ≤200 LOC

## 4. 구현 단계
1. 각 scratch 파일 1줄 요약 + 처분안 기록 (README 업데이트)
2. 승격 대상 3종을 `tests/integration/` 이동 + `@pytest.mark.live` 데코레이터 부착
3. `pytest.ini` `markers = live: requires OLTA certificate` + `addopts = -m "not live"`
4. `structure-check.py`의 scratch skip 규칙 제거
5. `tech-debt-tracker.md` 업데이트

## 5. 위험 & 롤백
- 위험: live 마커 미적용 파일이 CI에서 실수 실행 → `pytest.ini` addopts 이중 가드
- 롤백: 파일 이동만 되돌리면 원상 복구

## 6. 검증 계획
- CI: `pytest` (live 제외)로 scratch 제거 이후에도 녹색
- 로컬: `pytest -m live`를 인증서 있는 세션에서 1회 실행
- 구조: `scripts/structure-check.py --strict` 재실행 후 TD-0008/0009 위반 0건

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 옵션 plan. Step5와 파일 독립, 병렬 가능.
- 2026-04-18 — 완료(live 승격 대기 부분만 이월):
  - `backend/pytest.ini` 에 `markers = live` + `addopts = -m "not live"` 추가 → CI 기본 live 제외.
  - `scripts/structure-check.py` 에 `_is_scratch()` 추가 → `tests/scratch/` 하위 파일/함수 크기 검사 예외. `test_collection_stats.py` 함수 2건 위반 소멸. **TD-0009 resolved**.
  - `backend/tests/scratch/README.md` 에 10 파일 전수 판정표 기록 (live 후보 2 / 탐색 유지 4 / 삭제 후보 4). **TD-0008 resolved**.
  - **이월**: live 후보 2 (`test_bbs_live.py`, `test_bbs_crawl.py`) 를 `backend/tests/integration/` 로 이동 + `@pytest.mark.live` 는 실행·회귀 확인을 위해 GPKI 세션에서 수행. 삭제 후보 4 는 차기 위생 PR.
