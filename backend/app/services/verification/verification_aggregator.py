"""verification_aggregator.py — Plan 3 refactor.

기존 174줄 `aggregate` 함수를 `_aggregate_claims / _aggregate_sources / _aggregate_slots
/ _combine` 4함수로 분해 (TD-0004). `aggregate` 자체는 orchestration 만 담당.

5-tier 라벨은 `app.feature_flags.flags.confidence_tiers`로 v1(legacy 4종)/v2(5종) 전환.
반방향 coverage_score 는 aggregator 호출자가 optional로 주입 (기본 None, 미지원 경로).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app import feature_flags as _ff
from app.models.verification import VerificationResult


@dataclass
class _ClaimsAgg:
    weighted_scores: list[float]
    total_weight: float
    cited_claims: int
    verified_citation_claims: int
    supported_claims: int
    hallucinated: bool
    unsupported_count: int
    removed_claims: list[str]
    modified_claims: list[dict]
    warnings: list[str]
    critical_issues: list[str]


@dataclass
class _SourcesAgg:
    scores: list[float]
    cited_failures: int
    warnings: list[str]
    critical_issues: list[str]


@dataclass
class _SlotsAgg:
    scores: list[float]
    contradicted: int
    warnings: list[str]
    critical_issues: list[str]


class VerificationAggregator:

    def aggregate(
        self,
        source_verifications,
        content_claims,
        slot_verifications=None,
        *,
        coverage_score: Optional[float] = None,
    ) -> VerificationResult:
        settings = get_settings()
        slot_verifications = slot_verifications or []
        source_map = {item.source_id: item for item in source_verifications}

        c = self._aggregate_claims(content_claims, source_map, settings)
        s = self._aggregate_sources(source_verifications)
        sl = self._aggregate_slots(slot_verifications, settings)
        return self._combine(
            source_verifications, content_claims, slot_verifications,
            c, s, sl, settings, coverage_score,
        )

    def _aggregate_claims(self, content_claims, source_map, settings) -> _ClaimsAgg:
        acc = _ClaimsAgg([], 0.0, 0, 0, 0, False, 0, [], [], [], [])
        for claim in content_claims:
            adjusted = claim.confidence
            has_verified_citation = False
            if claim.cited_sources:
                acc.cited_claims += 1
                statuses = [source_map[sid].status for sid in claim.cited_sources if sid in source_map]
                has_verified_citation = bool(statuses) and all(st == "verified" for st in statuses)
                if any(st == "not_found" for st in statuses):
                    adjusted *= settings.aggregator_penalty_not_found
                if any(st == "mismatch" for st in statuses):
                    adjusted *= settings.aggregator_penalty_mismatch
                if any(st == "expired" for st in statuses):
                    adjusted *= settings.aggregator_penalty_expired
            else:
                adjusted *= settings.aggregator_penalty_no_citation
            weight = self._claim_weight(claim.claim_text)
            acc.weighted_scores.append(adjusted * weight)
            acc.total_weight += weight
            if claim.verification_status in {"supported", "partial"}:
                acc.supported_claims += 1
            if claim.verification_status == "supported" and has_verified_citation:
                acc.verified_citation_claims += 1
            if claim.verification_status == "hallucinated":
                acc.hallucinated = True
            if claim.verification_status in {"unsupported", "hallucinated"}:
                acc.unsupported_count += 1
            self._classify_claim_warning(claim, adjusted, acc)
        return acc

    def _classify_claim_warning(self, claim, adjusted, acc) -> None:
        if claim.verification_status == "hallucinated" or (
            claim.verification_status == "unsupported" and adjusted < 0.3
        ):
            acc.removed_claims.append(claim.claim_text)
            acc.critical_issues.append(f"제거 필요 주장: {claim.claim_text}")
        if claim.verification_status == "partial" and claim.corrected_text:
            acc.modified_claims.append({
                "original": claim.claim_text,
                "corrected": claim.corrected_text,
                "reason": claim.detail,
            })
        if claim.verification_status == "unsupported" and adjusted >= 0.3:
            acc.warnings.append(f"⚠️ 확인 필요: {claim.claim_text}")
        elif not claim.cited_sources and adjusted < 0.3:
            acc.warnings.append(f"⚠️ 직접 출처 없음: {claim.claim_text}")
            acc.critical_issues.append(f"직접 출처 부족: {claim.claim_text}")

    def _aggregate_sources(self, source_verifications) -> _SourcesAgg:
        acc = _SourcesAgg([], 0, [], [])
        for source in source_verifications:
            acc.scores.append(self._source_score(source.status))
            if source.status in {"not_found", "mismatch"}:
                acc.warnings.append(f"⚠️ 출처 검증 실패: {source.source_id}")
                acc.critical_issues.append(f"출처 검증 실패: {source.source_id} ({source.status})")
                acc.cited_failures += 1
            elif source.status == "expired":
                acc.warnings.append(f"⚠️ 최신성 확인 필요 출처: {source.source_id}")
        return acc

    def _aggregate_slots(self, slot_verifications, settings) -> _SlotsAgg:
        acc = _SlotsAgg([], 0, [], [])
        for slot in slot_verifications:
            adjusted = slot.confidence
            if slot.status == "contradicted":
                adjusted *= settings.aggregator_slot_contradicted
                acc.warnings.append(f"⚠️ 근거 묶음 충돌: {slot.slot_id}")
                acc.critical_issues.append(f"근거 묶음 충돌: {slot.slot_id}")
                acc.contradicted += 1
            elif slot.status == "unused":
                adjusted *= settings.aggregator_slot_unused
                acc.warnings.append(f"⚠️ 활용되지 않은 근거 묶음: {slot.slot_id}")
            elif slot.status == "partial":
                adjusted *= settings.aggregator_slot_partial
            acc.scores.append(adjusted)
        return acc

    def _combine(self, source_verifications, content_claims, slot_verifications,
                 c: _ClaimsAgg, s: _SourcesAgg, sl: _SlotsAgg, settings,
                 coverage_score: Optional[float]) -> VerificationResult:
        claim_conf = sum(c.weighted_scores) / c.total_weight if c.total_weight else 0.0
        src_conf = sum(s.scores) / len(s.scores) if s.scores else 0.0
        slot_conf = sum(sl.scores) / len(sl.scores) if sl.scores else 0.0
        citation_coverage = c.cited_claims / len(content_claims) if content_claims else 0.0
        verified_citation_ratio = c.verified_citation_claims / c.cited_claims if c.cited_claims else 0.0
        supported_ratio = c.supported_claims / len(content_claims) if content_claims else 0.0

        overall = self._weighted_overall(
            claim_conf, src_conf, slot_conf, content_claims, source_verifications,
            slot_verifications, settings,
        )
        warnings = list(c.warnings + s.warnings + sl.warnings)
        critical = list(c.critical_issues + s.critical_issues + sl.critical_issues)
        overall = self._apply_caps(
            overall, c, s, sl, slot_conf, citation_coverage, verified_citation_ratio,
            supported_ratio, content_claims, slot_verifications, warnings, critical, settings,
        )
        overall = max(0.0, min(1.0, overall))
        label, tier = self._classify_tier(overall, settings)

        return VerificationResult(
            source_verifications=source_verifications,
            content_claims=content_claims,
            slot_verifications=slot_verifications,
            overall_confidence=round(overall, 2),
            claim_confidence=round(claim_conf, 2),
            source_confidence=round(src_conf, 2),
            slot_confidence=round(slot_conf, 2),
            citation_coverage=round(citation_coverage, 2),
            verified_citation_ratio=round(verified_citation_ratio, 2),
            supported_claim_ratio=round(supported_ratio, 2),
            coverage_score=coverage_score,
            confidence_label=label,
            confidence_tier=tier,
            removed_claims=c.removed_claims,
            modified_claims=c.modified_claims,
            warnings=list(dict.fromkeys(warnings)),
            critical_issues=list(dict.fromkeys(critical)),
        )

    def _weighted_overall(self, claim_conf, src_conf, slot_conf,
                          content_claims, source_verifications, slot_verifications,
                          settings) -> float:
        comps = []
        if content_claims:
            comps.append((claim_conf, settings.aggregator_claim_weight))
        if source_verifications:
            comps.append((src_conf, settings.aggregator_source_weight))
        if slot_verifications:
            comps.append((slot_conf, settings.aggregator_slot_weight))
        total = sum(w for _, w in comps)
        return sum(sc * w for sc, w in comps) / total if total else 0.0

    def _apply_caps(self, overall, c: _ClaimsAgg, s: _SourcesAgg, sl: _SlotsAgg,
                    slot_conf, citation_coverage, verified_citation_ratio, supported_ratio,
                    content_claims, slot_verifications, warnings, critical, settings) -> float:
        if c.hallucinated:
            overall = min(overall, settings.aggregator_cap_hallucinated)
        elif content_claims and c.unsupported_count >= max(1, len(content_claims) // 2):
            overall = min(overall, settings.aggregator_cap_unsupported_heavy)
        if s.cited_failures:
            overall = min(overall, settings.aggregator_cap_source_failure)
        if slot_verifications and slot_conf < 0.35:
            overall = min(overall, settings.aggregator_cap_slot_gap)
        if content_claims and citation_coverage < 0.5:
            warnings.append("⚠️ 직접 출처가 연결된 주장 비율이 낮습니다.")
            critical.append("직접 출처 커버리지 부족")
            overall = min(overall, settings.aggregator_cap_low_citation_coverage)
        if c.cited_claims and verified_citation_ratio < 0.6:
            warnings.append("⚠️ 검증된 출처에 직접 연결된 주장 비율이 낮습니다.")
            critical.append("검증된 출처 연결 비율 부족")
            overall = min(overall, settings.aggregator_cap_low_verified_citation_ratio)
        if content_claims and supported_ratio < 0.5:
            warnings.append("⚠️ 뒷받침되는 주장 비율이 낮습니다.")
            critical.append("supported 주장 비율 부족")
            overall = min(overall, settings.aggregator_cap_low_supported_ratio)
        return overall

    def _classify_tier(self, overall: float, settings) -> tuple[str, str]:
        """Plan 3: v2는 5-tier, v1은 legacy 4-tier 유지.
        반환: (display_label, tier_enum) — 프런트 legacy는 label, 신 계약은 tier 사용."""
        if _ff.flags.confidence_tiers == "v2":
            if overall >= settings.confidence_very_high:
                return "매우 높음", "very_high"
            if overall >= settings.confidence_high:
                return "높음", "high"
            if overall >= 0.55:
                return "보통", "medium"
            if overall >= settings.confidence_medium:
                return "낮음", "low"
            return "매우 낮음", "very_low"
        # v1 (legacy)
        if overall >= settings.confidence_very_high:
            return "매우 높음", "very_high"
        if overall >= settings.confidence_high:
            return "높음", "high"
        if overall >= settings.confidence_medium:
            return "보통", "medium"
        return "낮음", "low"

    def _claim_weight(self, claim_text: str) -> float:
        weight = 1.0
        if re.search(r"제\d+조", claim_text):
            weight += 0.3
        if re.search(r"\d+[억만천백]?원|\d+%|\d+분의\s*\d+", claim_text):
            weight += 0.2
        return weight

    def _source_score(self, status: str) -> float:
        scores = {"verified": 1.0, "expired": 0.45, "mismatch": 0.15, "not_found": 0.0}
        return scores.get(status, 0.0)


verification_aggregator = VerificationAggregator()
