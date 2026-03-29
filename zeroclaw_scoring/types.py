from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zeroclaw_scoring.tiers import Tier
    from hive_mind_oracle.types import OracleScoreSnapshotV1, AttributionOutcomeV1


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


def from_snapshot(msg: "OracleScoreSnapshotV1") -> "OraclePayload":
    """
    Adapter: converts OracleScoreSnapshotV1 from the Hive Mind Oracle Routing Adapter
    into an OraclePayload for this scoring module.

    Compatible with: github.com/P-U-C/hive-mind-oracle-adapter
    Wire format: spi.oracle.v1
    """
    return OraclePayload(
        operator_id=msg.operator_id,
        raw_karma=msg.raw_karma,
        confidence_lower=msg.confidence_interval.lower,
        confidence_upper=msg.confidence_interval.upper,
        oracle_quality_score=msg.oracle_quality_score,
        effective_sample_size=msg.effective_sample_size,
        oracle_count=1,  # single snapshot = 1 oracle; aggregate oracle_count externally
        timestamp=msg.timestamp,
        domain=msg.domain,
        oracle_state=msg.oracle_state.value if hasattr(msg.oracle_state, 'value') else str(msg.oracle_state),
    )


def from_attribution(msg: "AttributionOutcomeV1", snapshot: "OracleScoreSnapshotV1 | None" = None) -> "OraclePayload":
    """
    Adapter: converts AttributionOutcomeV1 (realized outcome) into an OraclePayload.

    Note: AttributionOutcomeV1 represents a realized outcome event, not a full oracle score.
    If a prior snapshot is available, it is used to populate oracle metadata.
    If no snapshot is provided, oracle_count and effective_sample_size default conservatively.

    Compatible with: github.com/P-U-C/hive-mind-oracle-adapter
    Wire format: spi.oracle.v1
    """
    # Derive karma from Brier score improvement (lower realized = better)
    brier_improvement = msg.baseline_brier - msg.realized_brier
    derived_karma = max(0.0, min(1.0, 0.5 + brier_improvement * 2.0))

    # Use snapshot metadata if available
    if snapshot is not None:
        return OraclePayload(
            operator_id=msg.operator_id,
            raw_karma=derived_karma,
            confidence_lower=snapshot.confidence_interval.lower,
            confidence_upper=snapshot.confidence_interval.upper,
            oracle_quality_score=snapshot.oracle_quality_score,
            effective_sample_size=snapshot.effective_sample_size,
            oracle_count=1,
            timestamp=msg.timestamp,
            domain=msg.domain,
            oracle_state=snapshot.oracle_state.value if hasattr(snapshot.oracle_state, 'value') else str(snapshot.oracle_state),
            karma_delta=getattr(msg, 'karma_delta', 0.0),
            baseline_brier=msg.baseline_brier,
            realized_brier=msg.realized_brier,
        )

    # Conservative defaults when no snapshot context available
    return OraclePayload(
        operator_id=msg.operator_id,
        raw_karma=derived_karma,
        confidence_lower=0.3,
        confidence_upper=0.7,
        oracle_quality_score=0.5,
        effective_sample_size=10,
        oracle_count=1,
        timestamp=msg.timestamp,
        domain=msg.domain,
        oracle_state="provisional",
        karma_delta=getattr(msg, 'karma_delta', 0.0),
        baseline_brier=msg.baseline_brier,
        realized_brier=msg.realized_brier,
    )


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
