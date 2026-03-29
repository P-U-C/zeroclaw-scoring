"""
Zeroclaw Operator Scoring Module — unit tests
"""
import time
import pytest

from zeroclaw_scoring import score_operators, OraclePayload, Tier
from zeroclaw_scoring.tiers import classify_tier
from zeroclaw_scoring.digest import compute_operator_digest
from zeroclaw_scoring.degradation import check_degradation


def make_payload(**kwargs) -> OraclePayload:
    defaults = dict(
        operator_id="op-1",
        raw_karma=0.75,
        confidence_lower=0.70,
        confidence_upper=0.80,
        oracle_quality_score=0.85,
        effective_sample_size=20,
        oracle_count=3,
        timestamp=time.time(),
        domain="onchain",
        oracle_state="verified",
    )
    defaults.update(kwargs)
    return OraclePayload(**defaults)


# --- Tier classification ---

def test_tier_oracle_verified():
    tier = classify_tier(karma=0.85, confidence_mid=0.85, oracle_count=3)
    assert tier == Tier.ORACLE_VERIFIED


def test_tier_partially_verified():
    tier = classify_tier(karma=0.55, confidence_mid=0.55, oracle_count=1)
    assert tier == Tier.PARTIALLY_VERIFIED


def test_tier_unverified():
    tier = classify_tier(karma=0.30, confidence_mid=0.30, oracle_count=1)
    assert tier == Tier.UNVERIFIED


# --- Scoring order ---

def test_score_ordering_multiple_operators():
    now = time.time()
    payloads = [
        make_payload(operator_id="op-low", raw_karma=0.30, confidence_lower=0.20, confidence_upper=0.40),
        make_payload(operator_id="op-high", raw_karma=0.90, confidence_lower=0.85, confidence_upper=0.95, oracle_count=3),
        make_payload(operator_id="op-mid", raw_karma=0.60, confidence_lower=0.55, confidence_upper=0.65),
    ]
    result = score_operators(payloads)
    ids = [op.operator_id for op in result.operators]
    assert ids.index("op-high") < ids.index("op-mid") < ids.index("op-low")
    assert result.operators[0].rank == 1


# --- Degradation ---

def test_degraded_stale_oracle_fallback():
    stale_ts = time.time() - 7200  # 2 hours ago
    payloads = [make_payload(timestamp=stale_ts)]
    result = score_operators(payloads, staleness_threshold_seconds=3600.0)
    op = result.operators[0]
    assert op.degraded is True
    assert "stale" in op.degradation_reason


def test_degraded_oracle_state_suspended():
    payloads = [make_payload(oracle_state="suspended")]
    result = score_operators(payloads)
    op = result.operators[0]
    assert op.degraded is True


def test_empty_payload_returns_empty_result():
    result = score_operators([])
    assert result.total_operators == 0
    assert result.operators == []
    assert result.degraded_count == 0
    assert result.policy_version == "zeroclaw.scoring.v1"


def test_malformed_karma_rejected():
    payloads = [make_payload(raw_karma=1.5)]
    result = score_operators(payloads)
    op = result.operators[0]
    assert op.degraded is True
    assert "karma" in op.degradation_reason.lower()


def test_tied_score_resolution():
    # Same karma + confidence + oracle_count → same trust_score → sorted by operator_id
    payloads = [
        make_payload(operator_id="zebra", raw_karma=0.70, confidence_lower=0.65, confidence_upper=0.75, oracle_count=2),
        make_payload(operator_id="alpha", raw_karma=0.70, confidence_lower=0.65, confidence_upper=0.75, oracle_count=2),
    ]
    result = score_operators(payloads)
    assert result.operators[0].operator_id == "alpha"
    assert result.operators[1].operator_id == "zebra"


def test_deterministic_digest():
    p1 = make_payload(operator_id="op-1", raw_karma=0.75, confidence_lower=0.70, confidence_upper=0.80, oracle_count=3)
    p2 = make_payload(operator_id="op-1", raw_karma=0.75, confidence_lower=0.70, confidence_upper=0.80, oracle_count=3)
    p_diff = make_payload(operator_id="op-1", raw_karma=0.60, confidence_lower=0.70, confidence_upper=0.80, oracle_count=3)

    from zeroclaw_scoring.tiers import Tier as T
    d1 = compute_operator_digest(p1, 0.75, T.ORACLE_VERIFIED)
    d2 = compute_operator_digest(p2, 0.75, T.ORACLE_VERIFIED)
    d3 = compute_operator_digest(p_diff, 0.60, T.PARTIALLY_VERIFIED)

    assert d1 == d2
    assert d1 != d3


def test_result_digest_changes_with_scores():
    payloads_a = [make_payload(operator_id="op-1", raw_karma=0.80, oracle_count=3)]
    payloads_b = [make_payload(operator_id="op-1", raw_karma=0.50)]
    result_a = score_operators(payloads_a)
    result_b = score_operators(payloads_b)
    assert result_a.result_digest != result_b.result_digest


def test_degraded_count_in_result():
    now = time.time()
    stale_ts = now - 7200
    payloads = [
        make_payload(operator_id="good-1", raw_karma=0.80, oracle_count=3),
        make_payload(operator_id="good-2", raw_karma=0.70, oracle_count=2),
        make_payload(operator_id="stale-1", timestamp=stale_ts),
    ]
    result = score_operators(payloads, staleness_threshold_seconds=3600.0)
    assert result.degraded_count == 1
    assert result.total_operators == 3


def test_from_snapshot_adapter():
    """from_snapshot converts flat fields correctly."""
    from zeroclaw_scoring.types import OraclePayload, from_snapshot

    class FakeCI:
        lower = 0.70
        upper = 0.85

    class FakeSnapshot:
        operator_id = "op-snap-test"
        raw_karma = 0.78
        confidence_interval = FakeCI()
        oracle_quality_score = 0.91
        effective_sample_size = 120
        timestamp = time.time()
        domain = "onchain"
        oracle_state = type('S', (), {'value': 'verified'})()

    payload = from_snapshot(FakeSnapshot())
    assert payload.operator_id == "op-snap-test"
    assert payload.raw_karma == 0.78
    assert payload.confidence_lower == 0.70
    assert payload.confidence_upper == 0.85
    assert payload.oracle_state == "verified"


def test_from_attribution_adapter_no_snapshot():
    """from_attribution without snapshot uses conservative defaults."""
    from zeroclaw_scoring.types import from_attribution

    class FakeOutcome:
        operator_id = "op-attr-test"
        baseline_brier = 0.25
        realized_brier = 0.10
        timestamp = time.time()
        domain = "onchain"
        karma_delta = 0.05

    payload = from_attribution(FakeOutcome())
    assert payload.operator_id == "op-attr-test"
    assert payload.raw_karma > 0.5  # positive Brier improvement → karma above 0.5
    assert payload.oracle_state == "provisional"
    assert payload.oracle_count == 1


def test_upstream_tier_mapping():
    """T2/T3 map to ORACLE_VERIFIED, T1 to PARTIALLY_VERIFIED, T0 to UNVERIFIED."""
    from zeroclaw_scoring.tiers import from_upstream_tier, Tier
    assert from_upstream_tier("T3") == Tier.ORACLE_VERIFIED
    assert from_upstream_tier("T2") == Tier.ORACLE_VERIFIED
    assert from_upstream_tier("T1") == Tier.PARTIALLY_VERIFIED
    assert from_upstream_tier("T0") == Tier.UNVERIFIED
    assert from_upstream_tier("unknown") == Tier.UNVERIFIED


def test_digest_changes_with_policy_version():
    """Same inputs but different policy version → different digest."""
    import time
    from zeroclaw_scoring.digest import compute_operator_digest
    from zeroclaw_scoring.types import OraclePayload
    from zeroclaw_scoring.tiers import Tier

    payload = OraclePayload(
        operator_id="op-policy-test",
        raw_karma=0.75,
        confidence_lower=0.70,
        confidence_upper=0.80,
        oracle_quality_score=0.90,
        effective_sample_size=100,
        oracle_count=2,
        timestamp=time.time(),
    )
    d1 = compute_operator_digest(payload, 0.75, Tier.ORACLE_VERIFIED, policy_version="zeroclaw.scoring.v1")
    d2 = compute_operator_digest(payload, 0.75, Tier.ORACLE_VERIFIED, policy_version="zeroclaw.scoring.v2")
    assert d1 != d2


def test_digest_changes_with_staleness_threshold():
    """Same inputs but different staleness threshold → different digest."""
    import time
    from zeroclaw_scoring.digest import compute_operator_digest
    from zeroclaw_scoring.types import OraclePayload
    from zeroclaw_scoring.tiers import Tier

    payload = OraclePayload(
        operator_id="op-staleness-test",
        raw_karma=0.70,
        confidence_lower=0.65,
        confidence_upper=0.75,
        oracle_quality_score=0.88,
        effective_sample_size=80,
        oracle_count=2,
        timestamp=time.time(),
    )
    d1 = compute_operator_digest(payload, 0.70, Tier.ORACLE_VERIFIED, staleness_threshold=3600.0)
    d2 = compute_operator_digest(payload, 0.70, Tier.ORACLE_VERIFIED, staleness_threshold=7200.0)
    assert d1 != d2


def test_tier_boundary_exactly_0_65():
    """Karma and confidence exactly at ORACLE_VERIFIED boundary."""
    from zeroclaw_scoring.tiers import classify_tier, Tier
    # Exactly at threshold with oracle_count >= 2 → should be ORACLE_VERIFIED
    tier = classify_tier(karma=0.65, confidence_mid=0.65, oracle_count=2)
    assert tier == Tier.ORACLE_VERIFIED
    # Just below threshold
    tier_below = classify_tier(karma=0.649, confidence_mid=0.65, oracle_count=2)
    assert tier_below != Tier.ORACLE_VERIFIED


def test_unavailable_oracle_state():
    """oracle_state='unverified' triggers degradation."""
    import time
    from zeroclaw_scoring import score_operators
    from zeroclaw_scoring.types import OraclePayload

    payload = OraclePayload(
        operator_id="op-unverified",
        raw_karma=0.80,
        confidence_lower=0.75,
        confidence_upper=0.85,
        oracle_quality_score=0.0,  # unverified oracle has quality 0
        effective_sample_size=50,
        oracle_count=1,
        timestamp=time.time(),
        oracle_state="unverified",
    )
    result = score_operators([payload])
    assert result.operators[0].degraded is True
