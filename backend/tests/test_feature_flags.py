"""feature_flags.py 기본 동작 확인."""
from __future__ import annotations

import os

import pytest

from app import feature_flags as ff


@pytest.fixture(autouse=True)
def _restore_env():
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)
    ff._reload_for_tests()


def test_defaults_match_spec():
    os.environ.pop("BBS_CONCURRENCY", None)
    os.environ.pop("RETRIEVAL_MODE", None)
    os.environ.pop("CONFIDENCE_TIERS", None)
    os.environ.pop("MAX_REVISION_ROUNDS", None)
    f = ff._reload_for_tests()
    assert f.bbs_concurrency == 4
    assert f.retrieval_mode == "hybrid"
    assert f.confidence_tiers == "v2"
    assert f.max_revision_rounds == 2
    assert f.sse_events_version == "v2"


def test_invalid_enum_falls_back_to_default():
    os.environ["RETRIEVAL_MODE"] = "invalid_mode"
    f = ff._reload_for_tests()
    assert f.retrieval_mode == "hybrid"


def test_env_override_applied():
    os.environ["BBS_CONCURRENCY"] = "1"
    os.environ["RETRIEVAL_MODE"] = "embedding"
    os.environ["MAX_REVISION_ROUNDS"] = "0"
    os.environ["VERIFY_MORPH"] = "1"
    f = ff._reload_for_tests()
    assert f.bbs_concurrency == 1
    assert f.retrieval_mode == "embedding"
    assert f.max_revision_rounds == 0
    assert f.verify_morph is True


def test_bad_int_falls_back_to_default():
    os.environ["BBS_CONCURRENCY"] = "not_a_number"
    f = ff._reload_for_tests()
    assert f.bbs_concurrency == 4


def test_bool_parsing():
    os.environ["CRAWL_CACHE_ENABLED"] = "false"
    f = ff._reload_for_tests()
    assert f.crawl_cache_enabled is False
    os.environ["CRAWL_CACHE_ENABLED"] = "yes"
    f = ff._reload_for_tests()
    assert f.crawl_cache_enabled is True
