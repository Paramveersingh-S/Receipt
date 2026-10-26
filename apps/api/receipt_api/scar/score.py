import datetime
import math
from typing import List
from receipt_api.schemas import EvidenceItem

# Evidence type base weights
EVIDENCE_TYPE_WEIGHTS = {
    "incident_fix": 1.0,
    "revert": 0.8,
    "review": 0.5,
    "comment": 0.3,
}

HALF_LIFE_DAYS = 180.0
LAMBDA_DECAY = math.log(2) / HALF_LIFE_DAYS


def calculate_constraint_confidence(
    evidence: List[EvidenceItem],
    reference_time: datetime.datetime = datetime.datetime.now(datetime.timezone.utc),
) -> float:
    """Compute confidence score for a constraint based on its evidence provenance.
    
    Formula:
    1. Base weight by evidence type: incident_fix (1.0) > revert (0.8) > review (0.5) > comment (0.3).
    2. Recency decay: exponential decay with 180-day half-life.
    3. Recurrence bonus: +0.08 per distinct evidence source (capped at +0.25).
    4. Capped strictly within [0.10, 1.00] with 2 decimal precision.
    """
    if not evidence:
        return 0.50

    weighted_sum = 0.0
    distinct_shas_or_urls = set()

    for item in evidence:
        w = EVIDENCE_TYPE_WEIGHTS.get(item.type, 0.4)
        
        # Recency decay
        if item.at:
            try:
                ev_time = datetime.datetime.fromisoformat(item.at.replace("Z", "+00:00"))
                days_old = max(0.0, (reference_time - ev_time).total_seconds() / 86400.0)
                decay = math.exp(-LAMBDA_DECAY * days_old)
            except Exception:
                decay = 1.0
        else:
            decay = 1.0

        weighted_sum += w * decay
        distinct_shas_or_urls.add(item.sha or item.url)

    # Recurrence bonus for multi-event corroboration
    recurrence_count = max(0, len(distinct_shas_or_urls) - 1)
    recurrence_bonus = min(0.25, recurrence_count * 0.08)

    # Normalize: single incident fix = 0.90, single revert = 0.80, single review = 0.70
    max_single_w = max(EVIDENCE_TYPE_WEIGHTS.get(item.type, 0.4) for item in evidence)
    base_confidence = 0.50 + (max_single_w * 0.35)
    
    final_score = base_confidence + recurrence_bonus
    # Bound between 0.10 and 1.00
    clamped = max(0.10, min(1.00, final_score))
    return round(clamped, 2)
