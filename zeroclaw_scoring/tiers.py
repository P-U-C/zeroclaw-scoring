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
