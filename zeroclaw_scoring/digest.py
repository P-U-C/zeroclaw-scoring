import hashlib
import json

from zeroclaw_scoring.types import OraclePayload, OperatorScore
from zeroclaw_scoring.tiers import Tier


def compute_operator_digest(payload: OraclePayload, trust_score: float, tier: Tier) -> str:
    """SHA-256 of canonical JSON (sorted keys, no whitespace) of deterministic inputs."""
    data = {
        "confidence_lower": payload.confidence_lower,
        "confidence_upper": payload.confidence_upper,
        "domain": payload.domain,
        "karma": payload.raw_karma,
        "operator_id": payload.operator_id,
        "tier": tier.value,
        "trust_score": trust_score,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_result_digest(operator_scores: list[OperatorScore]) -> str:
    """SHA-256 of all operator digests concatenated in rank order."""
    # Sort by rank to ensure deterministic order
    sorted_scores = sorted(operator_scores, key=lambda s: s.rank)
    joined = "".join(s.digest for s in sorted_scores)
    return hashlib.sha256(joined.encode()).hexdigest()
