from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zeroclaw_scoring.tiers import Tier


@dataclass
class OraclePayload:
    """Unified input — accepts either reputation_update or attribution_outcome format."""
    operator_id: str
    raw_karma: float              # [0,1] — from OracleScoreSnapshotV1
    confidence_lower: float       # from ConfidenceInterval.lower
    confidence_upper: float       # from ConfidenceInterval.upper
    oracle_quality_score: float   # [0,1]
    effective_sample_size: int
    oracle_count: int             # number of distinct oracles contributing
    timestamp: float              # unix epoch — used for staleness check
    domain: str = "onchain"
    oracle_state: str = "verified"  # verified/degraded/suspended/provisional/unverified
    # Attribution outcome fields (optional)
    karma_delta: float = 0.0
    baseline_brier: float = 0.25
    realized_brier: float = 0.25


@dataclass
class OperatorScore:
    operator_id: str
    trust_score: float            # [0, 1] composite score
    tier: "Tier"
    rank: int                     # 1 = highest ranked
    confidence: float             # midpoint of CI
    karma: float                  # input raw_karma
    digest: str                   # SHA-256 of deterministic inputs
    degraded: bool                # True if fallback scoring was applied
    degradation_reason: str       # empty string if not degraded
    scoring_notes: list[str] = field(default_factory=list)


@dataclass
class ScoringResult:
    operators: list[OperatorScore]   # sorted by rank (1 = best)
    policy_version: str              # "zeroclaw.scoring.v1"
    scored_at: float                 # unix timestamp
    total_operators: int
    degraded_count: int
    result_digest: str               # SHA-256 of all operator digests concatenated
