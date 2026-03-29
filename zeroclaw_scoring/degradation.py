from zeroclaw_scoring.types import OraclePayload


def check_degradation(
    payload: OraclePayload,
    now: float,
    staleness_threshold: float,
) -> tuple[bool, str]:
    """
    Check if oracle payload should be treated as degraded.

    Returns (is_degraded, reason). First matching condition wins.

    When degraded, the scorer applies a conservative baseline:
        trust_score = 0.25 (fixed neutral baseline — all degraded operators equal)
        tier = UNVERIFIED

    This represents "no confidence in oracle data" — the operator receives a
    score proportional only to raw karma at equal weight (0.5 coefficient),
    without oracle confidence boosting or tier multiplier enhancement.
    For fully missing data, raw_karma defaults to 0.5 (neutral), producing
    trust_score = 0.25 — below all non-degraded operators.
    """
    if payload.timestamp < now - staleness_threshold:
        return True, "stale oracle data"

    if payload.oracle_state in ("degraded", "suspended"):
        return True, f"oracle in {payload.oracle_state} state"

    if payload.oracle_quality_score < 0.3:
        return True, "oracle quality below minimum threshold"

    if payload.raw_karma < 0.0 or payload.raw_karma > 1.0:
        return True, "karma out of valid range"

    if payload.effective_sample_size < 5:
        return True, "insufficient sample size"

    return False, ""
