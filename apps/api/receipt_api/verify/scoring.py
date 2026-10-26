from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class ScoreBreakdown:
    behavior: float
    constraints: float
    test_strength: float
    regression: float
    browser: Optional[float] = None


@dataclass
class ScoringResult:
    score: int
    verdict: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
    breakdown: ScoreBreakdown
    hard_gate_triggered: Optional[str] = None


def calculate_score(
    behavior: float,
    constraints: float,
    test_strength: float,
    regression: float,
    browser: Optional[float] = None,
    has_regressions: bool = False,
    has_blocking_violations: bool = False,
    has_non_vacuous_proofs: bool = True,
    is_bugfix: bool = False,
) -> ScoringResult:
    """Calculate the transparent line-item score and verdict with hard gates.

    Formula (plan §B5):
      Weights: behavior 0.35, constraints 0.25, test_strength 0.20, regression 0.15, browser 0.05
      If browser is None, its 0.05 weight is proportionally redistributed to the others:
        behavior: 0.35 / 0.95 = 0.3684
        constraints: 0.25 / 0.95 = 0.2632
        test_strength: 0.20 / 0.95 = 0.2105
        regression: 0.15 / 0.95 = 0.1579

    Hard Gates:
      1. Any regression vs base commit -> Capped at REJECTED (score capped at <60 if higher)
      2. Any blocking constraint violated -> Capped at NEEDS_REVIEW (score <= 69)
      3. Bugfix with zero non-vacuous proofs -> Capped at NEEDS_REVIEW (score <= 69)

    Verdict Thresholds:
      >= 85: VERIFIED
      60 - 84: NEEDS_REVIEW
      < 60: REJECTED
    """
    behavior = max(0.0, min(1.0, behavior))
    constraints = max(0.0, min(1.0, constraints))
    test_strength = max(0.0, min(1.0, test_strength))
    regression = max(0.0, min(1.0, regression))

    if browser is not None:
        browser = max(0.0, min(1.0, browser))
        raw_score = 100.0 * (
            0.35 * behavior
            + 0.25 * constraints
            + 0.20 * test_strength
            + 0.15 * regression
            + 0.05 * browser
        )
    else:
        # Redistribute 0.05 weight proportionally
        raw_score = 100.0 * (
            (0.35 / 0.95) * behavior
            + (0.25 / 0.95) * constraints
            + (0.20 / 0.95) * test_strength
            + (0.15 / 0.95) * regression
        )

    score = int(round(raw_score))
    hard_gate: Optional[str] = None

    # Evaluate Hard Gates in order of severity
    if has_regressions:
        hard_gate = "Hard gate: Regressions detected vs base commit; capped at REJECTED"
        verdict = "REJECTED"
        if score >= 60:
            score = 59
    elif has_blocking_violations:
        hard_gate = "Hard gate: Blocking constraint violated; capped at NEEDS_REVIEW"
        if score > 69:
            score = 69
        verdict = "NEEDS_REVIEW"
    elif is_bugfix and not has_non_vacuous_proofs:
        hard_gate = "Hard gate: Bugfix with zero non-vacuous proofs; capped at NEEDS_REVIEW"
        if score > 69:
            score = 69
        verdict = "NEEDS_REVIEW"
    else:
        if score >= 85:
            verdict = "VERIFIED"
        elif score >= 60:
            verdict = "NEEDS_REVIEW"
        else:
            verdict = "REJECTED"

    breakdown = ScoreBreakdown(
        behavior=round(behavior, 2),
        constraints=round(constraints, 2),
        test_strength=round(test_strength, 2),
        regression=round(regression, 2),
        browser=round(browser, 2) if browser is not None else None,
    )

    return ScoringResult(
        score=score,
        verdict=verdict,
        breakdown=breakdown,
        hard_gate_triggered=hard_gate,
    )
