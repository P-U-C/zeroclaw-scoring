"""
scorer.py — Core scoring function for the Zeroclaw Operator Scoring Module.

Scoring formula:
    confidence_mid = (confidence_lower + confidence_upper) / 2
    trust_score = (0.6 * karma + 0.4 * confidence_mid) * tier_multiplier

Where tier_multiplier is:
    ORACLE_VERIFIED    → 1.0×  (karma ≥ 0.65, confidence_mid ≥ 0.65, oracle_count ≥ 2)
    PARTIALLY_VERIFIED → 0.7×  (karma ≥ 0.45, confidence_mid ≥ 0.45)
    UNVERIFIED         → 0.4×  (below thresholds)

Degraded fallback:
    When oracle data is stale, in a degraded/suspended state, or otherwise
    unreliable, ALL degraded operators receive trust_score = 0.25 (fixed neutral
    baseline) regardless of their oracle inputs. This ensures stale or degraded
    oracle evidence cannot influence relative ranking between degraded operators.
    Ties among degraded operators are broken lexicographically by operator_id.

Ranking:
    Operators sorted descending by trust_score. Ties broken by operator_id ascending.
    Rank 1 = highest priority for Zeroclaw engine routing.

Upstream compatibility:
    Use from_snapshot(OracleScoreSnapshotV1) and from_attribution(AttributionOutcomeV1)
    from zeroclaw_scoring.types to convert directly from the Hive Mind Oracle Routing
    Adapter wire format (spi.oracle.v1) into OraclePayload for this scorer.
    See: github.com/P-U-C/hive-mind-oracle-adapter
"""
import time
import uuid

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
    run_id = str(uuid.uuid4())

    if not payloads:
        empty_digest = compute_result_digest([])
        return ScoringResult(
            operators=[],
            policy_version=POLICY_VERSION,
            scored_at=now,
            total_operators=0,
            degraded_count=0,
            result_digest=empty_digest,
            score_digest=empty_digest,
            run_id=run_id,
        )

    scored: list[OperatorScore] = []
    degraded_count = 0

    for payload in payloads:
        notes: list[str] = []
        is_degraded, degradation_reason = check_degradation(payload, now, staleness_threshold_seconds)

        if is_degraded:
            degraded_count += 1
            # True neutral baseline: all degraded operators receive the same
            # score (0.25) regardless of oracle inputs. Stale/degraded oracle
            # data should not influence relative ranking between degraded ops.
            # Tie-breaking within degraded operators is by operator_id (lexical).
            trust_score = 0.25
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

        digest = compute_operator_digest(
            payload, trust_score, tier,
            policy_version=POLICY_VERSION,
            staleness_threshold=staleness_threshold_seconds,
        )
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
        score_digest=result_digest,
        run_id=run_id,
    )
