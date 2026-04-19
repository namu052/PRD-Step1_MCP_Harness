# 03 — Verification Tiers, Bidirectional Check, Multi-round Revision

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead, frontend lead
**Related**: product-specs/overview, exec-plans/active/backend-step7-verification-multiround-tiers-registry, design-docs/02-hybrid-retrieval-and-domain-priors

## Problem
- `verification_aggregator.py:aggregate`가 174줄 단일 함수 → 가중치 튜닝·테스트 불가 (TD-0004)
- 신뢰도 tier가 3단계(`높음/보통/낮음`)뿐이라 프런트 `ConfidenceBadge`가 실제 confidence 값과 **loosely coupled**
- 환각 탐지가 **claim → evidence 단방향**. 답변이 근거를 인용은 했으나 근거가 실제 뒷받침 안 하는 경우(**coverage 문제**)는 놓침
- revision 루프가 단일 라운드, `overall_confidence < target`이면 무조건 1회 시도 → 품질 향상 가능성이 남아도 종료, 반대로 얕은 차이에도 1라운드 추가되어 레이턴시 낭비
- `KEYWORD_PATTERN`, `CONTRADICTION_PAIRS`가 Python 소스에 하드코딩 → 운영 중 튜닝 불가

## Options
### Option A — aggregate 분해 + 5-tier + bidirectional + multi-round
pros: 품질·레이턴시 이중 승리 가능, 프런트 계약 재확정 기회
cons: 프런트 동기화 비용, 레이턴시 회귀 위험

### Option B — aggregate 분해만
pros: 저위험
cons: 품질 정체

### Option C — LLM-as-a-judge 전면 교체
pros: 구현 단순
cons: 비용 폭증, fallback 경로 상실, 검증 가능성 하락

## Decision
**Option A**. 단, 각 축에 feature flag를 두어 독립 비활성 가능.

### 5-tier + calibration
```
very_high : overall_confidence >= 0.90
high      : 0.75 <= c < 0.90
medium    : 0.55 <= c < 0.75
low       : 0.35 <= c < 0.55
very_low  : c < 0.35
```
- 임계값은 **골든셋 Brier score 최소화**로 초기 조정 (Plan 0 baseline 데이터 사용)
- legacy 3-tier 매핑: very_high+high→`높음`, medium→`보통`, low+very_low→`낮음`
- feature flag `CONFIDENCE_TIERS=v1` (기본 v2)

### Bidirectional hallucination check
```
claim → evidence : 기존. claim이 어떤 근거에 지지되는가
evidence → claim : 신규. 각 evidence_slot이 답변에 반영됐는지(coverage)

hallucination_rate = unsupported_claims / total_claims
coverage_score     = used_slots / total_high_prior_slots
```
`coverage_score`가 낮으면 revision 트리거 가중.

### Multi-round revision + early stopping
```
round 0: draft
loop round r in 1..MAX_REVISION_ROUNDS (기본 2):
    if overall_confidence >= target: break
    revise()
    if |Δ confidence| < 0.05: break       # early stopping
    if coverage_score 이전 라운드 대비 하락: rollback + break
```
- flag: `MAX_REVISION_ROUNDS=0`(비활성) | `1`(현재 동작) | `2`(기본)

### Rule registry (hot-reload)
```
backend/app/services/verification/rules/
  keywords.yml         # 지방세 도메인 용어
  contradictions.yml   # 모순 쌍
  domain_terms.yml     # 동의어/약어
```
- `watchdog`로 파일 변경 감지, 다음 호출부터 적용
- `VERIFY_MORPH=1`일 때 `kiwipiepy` 형태소 분석으로 overlap 계산 정밀화. 기본 `0`.

### aggregate 분해
```python
class VerificationAggregator:
    def aggregate(self, sources, claims, slots) -> VerificationResult:
        weighted = self._claim_weight(claims, sources)      # ≤50 lines
        source_score = self._source_score(sources)          # ≤50 lines
        slot_score = self._slot_cap(slots)                  # ≤50 lines
        return self._combine(weighted, source_score, slot_score)  # ≤50 lines
```

## Consequences
- **+** `hallucination_rate` 목표 ≤ 0.05 달성 경로 확보
- **+** revision 레이턴시는 early stopping으로 평균 -20% 기대(2라운드 진입 소수)
- **+** TD-0004 해소
- **+** 프런트 UI는 `CONFIDENCE_TIERS=v2` 전환 시 label 맵핑만 교체
- **−** 레지스트리 YAML 관리 필요 — 초기 항목 대부분은 기존 상수 이전이라 작업량은 M
- **−** 2라운드 revision이 간혹 레이턴시 폭증 → `MAX_REVISION_ROUNDS=1` 폴백 유지
- neutral: 형태소 플래그는 CI off, 로컬/본번은 개별 튜닝

## Follow-ups
- `exec-plans/active/backend-step7-verification-multiround-tiers-registry.md`
- 프런트 `ConfidenceBadge` label 맵핑 교체는 frontend-step2 plan(미생성)에서 처리. 본 문서가 계약 원본.
- 형태소 분석 전면 도입은 CI 빌드 시간과 OS별 설치 복잡성 해결 후 재평가
