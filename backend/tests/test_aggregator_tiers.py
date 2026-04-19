"""Plan 3 — verification_aggregator 5-tier classifier 및 early-stopping signal 검증."""
from __future__ import annotations

import os

import pytest

from app import feature_flags as ff
from app.models.evidence import SlotVerification
from app.models.verification import ContentClaim, SourceVerification
from app.services.verification.verification_aggregator import (
    VerificationAggregator,
    verification_aggregator,
)


@pytest.fixture(autouse=True)
def _restore_env():
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)
    ff._reload_for_tests()


def _make_claims(confidences: list[float], status: str = "supported") -> list[ContentClaim]:
    return [
        ContentClaim(
            claim_text=f"claim-{i}",
            cited_sources=["s1"],
            verification_status=status,
            confidence=c,
        )
        for i, c in enumerate(confidences)
    ]


def _make_sources(statuses: list[str]) -> list[SourceVerification]:
    return [SourceVerification(source_id=f"s{i}", status=st) for i, st in enumerate(statuses)]


def test_v2_has_very_low_tier():
    os.environ["CONFIDENCE_TIERS"] = "v2"
    ff._reload_for_tests()
    # 모든 것이 틀린 경우 → 매우 낮음으로 분류
    claims = _make_claims([0.05, 0.05, 0.05], status="hallucinated")
    sources = _make_sources(["not_found", "not_found"])
    result = VerificationAggregator().aggregate(sources, claims)
    assert result.confidence_tier == "very_low"
    assert result.confidence_label == "매우 낮음"


def test_v1_caps_at_low():
    os.environ["CONFIDENCE_TIERS"] = "v1"
    ff._reload_for_tests()
    claims = _make_claims([0.05, 0.05, 0.05], status="hallucinated")
    sources = _make_sources(["not_found", "not_found"])
    result = VerificationAggregator().aggregate(sources, claims)
    assert result.confidence_tier == "low"
    assert result.confidence_label == "낮음"


def test_v2_very_high_tier():
    os.environ["CONFIDENCE_TIERS"] = "v2"
    ff._reload_for_tests()
    claims = _make_claims([0.95, 0.95], status="supported")
    sources = _make_sources(["verified", "verified"])
    slots = [SlotVerification(slot_id="sl1", status="used", confidence=0.95, detail="")]
    result = VerificationAggregator().aggregate(sources, claims, slots)
    assert result.confidence_tier == "very_high"
    assert result.confidence_label == "매우 높음"


def test_coverage_score_injected_when_provided():
    claims = _make_claims([0.9], status="supported")
    sources = _make_sources(["verified"])
    result = verification_aggregator.aggregate(sources, claims, coverage_score=0.73)
    assert result.coverage_score == 0.73


def test_coverage_score_defaults_to_none():
    claims = _make_claims([0.9], status="supported")
    sources = _make_sources(["verified"])
    result = verification_aggregator.aggregate(sources, claims)
    assert result.coverage_score is None


def test_hallucinated_caps_overall():
    claims = _make_claims([0.95, 0.95, 0.95], status="supported")
    claims[0].verification_status = "hallucinated"
    sources = _make_sources(["verified"])
    result = verification_aggregator.aggregate(sources, claims)
    # hallucinated 1건 있으면 aggregator_cap_hallucinated(0.34) 으로 제한
    assert result.overall_confidence <= 0.34
