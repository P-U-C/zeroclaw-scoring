"""
tiers.py — Trust tier classification for the Zeroclaw Operator Scoring Module.

Tier boundaries (downstream projection from upstream T0-T3):
    ORACLE_VERIFIED    ← upstream T2/T3: karma ≥ 0.65, confidence_mid ≥ 0.65, oracle_count ≥ 2
    PARTIALLY_VERIFIED ← upstream T1:   karma ≥ 0.45, confidence_mid ≥ 0.45
    UNVERIFIED         ← upstream T0:   below thresholds

Tier multipliers applied to base trust score:
    ORACLE_VERIFIED    → 1.0×
    PARTIALLY_VERIFIED → 0.7×
    UNVERIFIED         → 0.4×

Boundary rationale:
    0.65 threshold: aligns with "high-confidence verified" in the upstream oracle model
    (T2 karma floor). Requires multi-oracle confirmation (oracle_count ≥ 2) to prevent
    single-oracle inflation.

    0.45 threshold: aligns with "provisional" in the upstream model (T1 karma floor).
    Single oracle sufficient but carries reduced routing weight via 0.7× multiplier.

    Below 0.45: No meaningful oracle endorsement. Routed at minimum weight (0.4×) to
    allow participation without privileged access.

Upstream T0-T3 mapping: see UPSTREAM_TIER_MAP and from_upstream_tier() below.
"""
from enum import Enum


class Tier(Enum):
    ORACLE_VERIFIED = "oracle-verified"        # karma >= 0.65 AND confidence_mid >= 0.65 AND oracle_count >= 2
    PARTIALLY_VERIFIED = "partially-verified"  # karma >= 0.45 AND confidence_mid >= 0.45
    UNVERIFIED = "unverified"                  # below thresholds


TIER_MULTIPLIERS: dict[Tier, float] = {
    Tier.ORACLE_VERIFIED: 1.0,
    Tier.PARTIALLY_VERIFIED: 0.7,
    Tier.UNVERIFIED: 0.4,
}


def classify_tier(karma: float, confidence_mid: float, oracle_count: int) -> Tier:
    """Classify operator tier based on karma, confidence midpoint, and oracle count."""
    if karma >= 0.65 and confidence_mid >= 0.65 and oracle_count >= 2:
        return Tier.ORACLE_VERIFIED
    if karma >= 0.45 and confidence_mid >= 0.45:
        return Tier.PARTIALLY_VERIFIED
    return Tier.UNVERIFIED


# ------------------------------------------------------------------
# Upstream T0-T3 compatibility mapping
# ------------------------------------------------------------------
# The Hive Mind Oracle Routing Adapter uses T0-T3 tiers with these thresholds:
#   T3: karma >= 0.80, effective_sample_size >= 100, oracle_count >= 3  (multiplier 2.0x)
#   T2: karma 0.60-0.79, effective_sample_size >= 50                    (multiplier 1.5x)
#   T1: karma 0.40-0.59, effective_sample_size >= 20                    (multiplier 1.2x)
#   T0: karma < 0.40                                                     (multiplier 1.0x)
#
# This module uses a downstream projection of those tiers for Zeroclaw routing:
#   ORACLE_VERIFIED    ← T2 + T3 (high confidence, multi-oracle confirmed)
#   PARTIALLY_VERIFIED ← T1      (provisional, single oracle or low sample)
#   UNVERIFIED         ← T0      (unknown or degraded)
#
# This is an intentional projection layer, not a replacement for the upstream engine.

UPSTREAM_TIER_MAP = {
    "T3": Tier.ORACLE_VERIFIED,
    "T2": Tier.ORACLE_VERIFIED,
    "T1": Tier.PARTIALLY_VERIFIED,
    "T0": Tier.UNVERIFIED,
}


def from_upstream_tier(upstream_tier: str) -> Tier:
    """Map upstream T0-T3 tier string to Zeroclaw scoring tier."""
    return UPSTREAM_TIER_MAP.get(upstream_tier.upper(), Tier.UNVERIFIED)
