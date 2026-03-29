import hashlib
import json

from zeroclaw_scoring.types import OraclePayload, OperatorScore
from zeroclaw_scoring.tiers import Tier


def compute_operator_digest(
    payload: OraclePayload,
    trust_score: float,
    tier: Tier,
    policy_version: str = "zeroclaw.scoring.v1",
    staleness_threshold: float = 3600.0,
) -> str:
    """
    SHA-256 digest of deterministic scoring inputs + policy context.

    Includes: operator_id, confidence_lower, confidence_upper, domain, karma,
    tier, trust_score, oracle_state, oracle_quality_score, effective_sample_size,
    degradation_reason, policy_version, staleness_threshold.

    Excludes: scored_at, rank (derived), degraded (derived from reason).

    Two runs under different policy contexts will produce different digests
    even if the final trust_score and tier happen to match.
    """
    canonical = json.dumps({
        "confidence_lower": round(payload.confidence_lower, 8),
        "confidence_upper": round(payload.confidence_upper, 8),
        "domain": payload.domain,
        "effective_sample_size": payload.effective_sample_size,
        "karma": round(payload.raw_karma, 8),
        "operator_id": payload.operator_id,
        "oracle_quality_score": round(payload.oracle_quality_score, 8),
        "oracle_state": payload.oracle_state,
        "policy_version": policy_version,
        "staleness_threshold": staleness_threshold,
        "tier": tier.value,
        "trust_score": round(trust_score, 8),
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_result_digest(operator_scores: list[OperatorScore]) -> str:
    """SHA-256 of all operator digests concatenated in rank order."""
    # Sort by rank to ensure deterministic order
    sorted_scores = sorted(operator_scores, key=lambda s: s.rank)
    joined = "".join(s.digest for s in sorted_scores)
    return hashlib.sha256(joined.encode()).hexdigest()
