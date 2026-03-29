import time

from zeroclaw_scoring.types import OraclePayload, OperatorScore, ScoringResult
from zeroclaw_scoring.tiers import Tier, TIER_MULTIPLIERS, classify_tier
from zeroclaw_scoring.degradation import check_degradation
from zeroclaw_scoring.digest import compute_operator_digest, compute_result_digest

POLICY_VERSION = "zeroclaw.scoring.v1"


def score_operators(
    payloads: list[OraclePayload],
    staleness_threshold_seconds: float = 3600.0,
) -> ScoringResult:
    """Score a list of oracle payloads and return a ranked ScoringResult."""
    now = time.time()

    if not payloads:
        return ScoringResult(
            operators=[],
            policy_version=POLICY_VERSION,
            scored_at=now,
            total_operators=0,
            degraded_count=0,
            result_digest=compute_result_digest([]),
        )

    scored: list[OperatorScore] = []
    degraded_count = 0

    for payload in payloads:
        notes: list[str] = []
        is_degraded, degradation_reason = check_degradation(payload, now, staleness_threshold_seconds)

        if is_degraded:
            degraded_count += 1
            # Fallback scoring: baseline equal-weight
            trust_score = 0.5 * payload.raw_karma
            # Clamp for out-of-range karma
            trust_score = max(0.0, trust_score)
            tier = Tier.UNVERIFIED
            notes.append(f"degraded: {degradation_reason}")
        else:
            confidence_mid = (payload.confidence_lower + payload.confidence_upper) / 2
            tier = classify_tier(payload.raw_karma, confidence_mid, payload.oracle_count)
            multiplier = TIER_MULTIPLIERS[tier]
            trust_score = (0.6 * payload.raw_karma + 0.4 * confidence_mid) * multiplier
            notes.append(f"tier: {tier.value}")

        digest = compute_operator_digest(payload, trust_score, tier)
        confidence_mid_out = (payload.confidence_lower + payload.confidence_upper) / 2

        scored.append(OperatorScore(
            operator_id=payload.operator_id,
            trust_score=trust_score,
            tier=tier,
            rank=0,  # assigned below
            confidence=confidence_mid_out,
            karma=payload.raw_karma,
            digest=digest,
            degraded=is_degraded,
            degradation_reason=degradation_reason,
            scoring_notes=notes,
        ))

    # Sort: descending trust_score, then ascending operator_id for ties
    scored.sort(key=lambda s: (-s.trust_score, s.operator_id))

    # Assign ranks
    for i, op in enumerate(scored):
        op.rank = i + 1

    result_digest = compute_result_digest(scored)

    return ScoringResult(
        operators=scored,
        policy_version=POLICY_VERSION,
        scored_at=now,
        total_operators=len(scored),
        degraded_count=degraded_count,
        result_digest=result_digest,
    )
