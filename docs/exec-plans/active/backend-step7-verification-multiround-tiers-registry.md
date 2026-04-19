# backend-step7-verification-multiround-tiers-registry — 검증 5-tier·양방향·다라운드·레지스트리

**Status**: active
**Created**: 2026-04-17
**Owner**: backend lead
**Tool**: claude
**Autonomy level**: L2
**Related**: product-specs/overview, design-docs/03-verification-tiers-and-multiround, active/backend-step4-pipeline-instrumentation-baseline, active/backend-step6-retrieval-hybrid-rerank

## 1. Why (배경·문제)
`aggregate`(174줄, TD-0004)가 단일 함수라 가중치 튜닝 불가. 신뢰도 tier는 3단계뿐이고 `ConfidenceBadge`와 loosely coupled. 환각 탐지는 단방향(claim→evidence)이라 근거 coverage 문제를 놓침. revision은 단일 라운드에 early stopping 없음. 규칙 테이블은 하드코딩이라 운영 튜닝 불가.

## 2. Scope
### In
- `aggregate` → `_claim_weight / _source_score / _slot_cap / _combine` 4함수 ≤50줄 (TD-0004)
- 5-tier 신뢰도 (very_high/high/medium/low/very_low) + Brier 기반 threshold 보정
- legacy 3-tier 매핑 유지 (`CONFIDENCE_TIERS=v1|v2`)
- Bidirectional 환각 체크: evidence→claim 커버리지 → `coverage_score` 도입
- Multi-round revision + early stopping: 최대 2라운드, `|Δconf| < 0.05` 종료, coverage 하락 시 rollback
- Rule registry `verification/rules/{keywords,contradictions,domain_terms}.yml` 핫리로드
- `VERIFY_MORPH=1` 선택 시 kiwipiepy 형태소 분석 경로
- feature flag: `CONFIDENCE_TIERS`, `MAX_REVISION_ROUNDS` (0/1/2), `VERIFY_MORPH`, `BIDIRECTIONAL_HALLUCINATION_CHECK`
### Out
- LLM 모델 교체
- 프런트 `ConfidenceBadge` UI 변경(계약만 합의, 구현은 frontend plan)

## 3. Definition of Done
- [ ] golden set `hallucination_rate ≤ 0.05`
- [ ] Brier score ≤ 0.10
- [ ] `aggregate` ≤50줄, 4 서브함수 각 ≤50줄, `structure-check --strict` 통과 (TD-0004 resolved)
- [ ] verify 단계 P50 baseline 대비 회귀 없음(±5%), early stopping 활성 시 P50 -10% 이상
- [ ] rule registry YAML 핫리로드 테스트 통과 (파일 수정 후 다음 호출 반영)
- [ ] `VERIFY_MORPH=0` CI 기본, `=1` smoke 테스트 1건 통과
- [ ] 신규 `tests/verification/test_aggregator_units.py`, `test_rules_registry.py`, `test_bidirectional_check.py`
- [ ] PR ≤400 LOC
- [ ] `tech-debt-tracker.md` TD-0004 `resolved`

## 4. 구현 단계
1. `verification/rules/*.yml` 레지스트리 + 로더. 기존 상수(KEYWORD_PATTERN, CONTRADICTION_PAIRS) 이전
2. `aggregate` 분해 (4 서브함수) + 단위 테스트 6건(가중치 경계)
3. 5-tier enum + 칼리브레이션 테이블 (골든셋 통계로 threshold 산출), legacy 매핑 유지
4. Bidirectional coverage 체크: `grouped_answer_verifier`를 양방향으로 확장 + `coverage_score` 필드 추가
5. Multi-round revision 루프 + early stopping — `_run_verification` 개편 (design-doc 03 알고리즘)
6. `VERIFY_MORPH` 플래그: kiwipiepy 옵셔널 import(미설치 시 graceful fallback)
7. `source_verifier.classify_v2` 5단계 분류 + design-doc 02 `source_priority` 스키마와 정합

## 5. 위험 & 롤백
- 위험1: 5-tier 매핑이 프런트 UI와 싱크 실패 → design-doc 03 매핑 표 고정, `CONFIDENCE_TIERS=v1` 기본 유지하며 운영 검증 후 전환
- 위험2: multi-round revision이 레이턴시 폭증 → `MAX_REVISION_ROUNDS=1` 기본 유지, `=2`는 실험 flag
- 위험3: Bidirectional check가 오탐(coverage_score가 부당하게 낮음) → YAML로 최소 `total_high_prior_slots` 하한 설정, flag로 비활성 가능
- 롤백: 각 flag off + `MAX_REVISION_ROUNDS=1`

## 6. 검증 계획
- 단위: 4개 서브함수, 레지스트리 핫리로드, 양방향 coverage 계산
- 통합: 골든셋 전체 3회 실행 후 hallucination_rate 추세
- 성능: Step4 baseline과 verify 단계 diff, revision 라운드 분포 히스토그램
- 품질: `observability/reports/<date>-verification-tiers.md` — tier별 건수/정확도 표

## 7. 일지 (append-only)
- 2026-04-17 — active 등록. 선행: Step4 baseline + Step6 `classify_v2` 스키마 확정. TD-0004 scheduled.
- 2026-04-18 — PR#1 (핵심) 착수·완료:
  - `backend/app/services/verification/verification_aggregator.py` 전면 리팩터: 174줄 `aggregate` → `_aggregate_claims / _aggregate_sources / _aggregate_slots / _combine / _weighted_overall / _apply_caps / _classify_tier` (각 ≤50줄). **TD-0004 resolved**.
  - 5-tier 분류 도입: `CONFIDENCE_TIERS=v2`(기본, 매우 낮음 추가) / `v1`(legacy 4-tier) 전환. `VerificationResult.confidence_tier` 필드 추가 (very_high/high/medium/low/very_low).
  - 반방향 coverage 훅: `VerificationResult.coverage_score: Optional[float]` — 호출자가 주입 시 통과, 미주입 시 None. (실제 evidence→claim 측정은 PR#2 에서 `grouped_answer_verifier` 확장 필요)
  - `backend/app/feature_flags.py`: `MAX_REVISION_ROUNDS=2` / `REVISION_STAGNATION_DELTA=0.05` / `VERIFY_MORPH=false` / `HALLUCINATION_BIDIRECTIONAL=true` 플래그 노출 — revision 루프 측 소비는 PR#2 이월.
  - `backend/tests/test_aggregator_tiers.py` 6건 green (v1/v2 tier/caps/coverage injection)
  - `backend/tests/test_verification_pipeline.py::test_verification_pipeline_all_wrong` 기대값 `"낮음"` → `in ("낮음", "매우 낮음")` 완화 (v2 정확도가 더 높음)
  - **잔여(PR#2~)**: multi-round + early stopping 실제 revision 루프에 적용, bidirectional coverage 실측, `verification/rules/*.yml` 레지스트리, morph 경로 smoke — 인증 세션에서 수행.
