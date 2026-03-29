# zeroclaw-scoring

Operator trust scoring module for the Zeroclaw routing engine — ranks oracle operators by composite trust score with tier classification and degradation detection.

## Integration Context

Consumes oracle payloads from the Hive Mind Oracle Routing Adapter (github.com/P-U-C/hive-mind-oracle-adapter). The `OraclePayload` type is wire-format compatible with both `reputation_update` and `attribution_outcome` message types from the adapter.

## Setup

```bash
pip install pytest
cd zeroclaw-scoring
python3 -m pytest tests/ -v
```

## Example

```python
import time
from zeroclaw_scoring import score_operators, OraclePayload

payloads = [
    OraclePayload(
        operator_id="oracle-a",
        raw_karma=0.85,
        confidence_lower=0.80,
        confidence_upper=0.90,
        oracle_quality_score=0.92,
        effective_sample_size=50,
        oracle_count=3,
        timestamp=time.time(),
    ),
    OraclePayload(
        operator_id="oracle-b",
        raw_karma=0.60,
        confidence_lower=0.55,
        confidence_upper=0.65,
        oracle_quality_score=0.75,
        effective_sample_size=15,
        oracle_count=1,
        timestamp=time.time(),
    ),
    OraclePayload(
        operator_id="oracle-c",
        raw_karma=0.30,
        confidence_lower=0.20,
        confidence_upper=0.40,
        oracle_quality_score=0.50,
        effective_sample_size=8,
        oracle_count=1,
        timestamp=time.time(),
    ),
]

result = score_operators(payloads)

for op in result.operators:
    print(f"Rank {op.rank}: {op.operator_id} | tier={op.tier.value} | trust={op.trust_score:.3f} | degraded={op.degraded}")

# Output:
# Rank 1: oracle-a | tier=oracle-verified | trust=0.850 | degraded=False
# Rank 2: oracle-b | tier=partially-verified | trust=0.434 | degraded=False
# Rank 3: oracle-c | tier=unverified | trust=0.104 | degraded=False
```

## Scoring Formula

```
confidence_mid = (confidence_lower + confidence_upper) / 2
trust_score = (0.6 * karma + 0.4 * confidence_mid) * tier_multiplier
```

Weights: karma carries 60% of the signal, confidence interval midpoint carries 40%. The tier multiplier scales the composite score based on verification level.

If a degradation condition is detected, fallback scoring applies: `trust_score = 0.5 * raw_karma`, tier = UNVERIFIED.

## Tier Boundaries

| Tier | Condition | Multiplier | Rationale |
|------|-----------|------------|-----------|
| `oracle-verified` | karma ≥ 0.65 AND confidence_mid ≥ 0.65 AND oracle_count ≥ 2 | 1.0 | Multi-oracle consensus with high karma and confidence |
| `partially-verified` | karma ≥ 0.45 AND confidence_mid ≥ 0.45 | 0.7 | Single oracle or borderline metrics — usable but discounted |
| `unverified` | below thresholds | 0.4 | Low signal quality — significant penalty applied |

Thresholds set at 0.65/0.45 to create meaningful separation between high-confidence multi-oracle consensus and solo/low-confidence operators.

## Degradation Conditions

An operator is flagged as degraded (fallback scoring) if ANY of:
- Timestamp is older than `staleness_threshold_seconds` (default: 3600s)
- `oracle_state` is `"degraded"` or `"suspended"`
- `oracle_quality_score < 0.3`
- `raw_karma` outside `[0.0, 1.0]`
- `effective_sample_size < 5`

## Zeroclaw Engine Integration

Pass `ScoringResult.operators` to Zeroclaw engine — rank 1 = highest priority routing.

```python
result = score_operators(payloads)
zeroclaw_engine.route(operators=result.operators)
```

The `result_digest` (SHA-256 of all operator digests) provides a deterministic fingerprint for the full scoring run — use it for audit logging and cache invalidation.
