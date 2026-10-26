"""Ground truth held-out hidden tests for Receipt benchmarks.

These tests are NEVER shown to coding agents.
- FAILS on subtle bug implementation (catches float math, mis-rounding, and bad idempotency).
- PASSES on correct implementation.
"""

import os
import pytest
from shop.payments import MockPaymentGateway


def get_service():
    impl = os.getenv("COUPON_IMPL", "correct").lower()
    if impl == "subtle":
        from demo.seed.agent_diffs.coupon_subtle import SubtleCouponService
        return SubtleCouponService(), "subtle"
    else:
        from demo.seed.agent_diffs.coupon_correct import CorrectCouponService
        return CorrectCouponService(), "correct"


def test_fractional_cent_half_up_rounding_boundary():
    """Hidden test: 10% on $19.99 (1999 cents) = 199.9 cents -> must round to 200 cents.
    
    Subtle float truncation bug computes int(1999 * 0.1) = 199 cents (1 cent off!).
    Correct integer half-up computes (1999 * 1000 + 5000) // 10000 = 200 cents.
    """
    service, _ = get_service()
    res = service.apply_coupon("SAVE10", 1999)
    assert res["discount_cents"] == 200, (
        f"Rounding error: expected 200 cents (half-up from 199.9c), got {res['discount_cents']}c"
    )
    assert res["total_cents"] == 1799


def test_odd_penny_five_percent_rounding():
    """Hidden test: 5% (simulated through 15% - 10%) or 15% on $29.99 (2999 cents).
    
    2999 * 0.15 = 449.85 cents -> must round half-up to 450 cents.
    Subtle float truncation computes int(2999 * 0.15) = 449 cents (1 cent off!).
    """
    service, _ = get_service()
    res = service.apply_coupon("WELCOME15", 2999)
    assert res["discount_cents"] == 450, (
        f"Rounding error: expected 450 cents (half-up from 449.85c), got {res['discount_cents']}c"
    )
    assert res["total_cents"] == 2549


def test_checkout_retry_generates_distinct_attempt_idempotency_keys():
    """Hidden test: payment gateway retries must use distinct attempt keys per try."""
    service, impl_type = get_service()
    gateway = MockPaymentGateway()

    if impl_type == "subtle":
        # Subtle service hardcodes static key for all retries
        tx1 = service.process_checkout_retry(gateway, amount_cents=1500, card_token="tok_visa_valid", attempt=1)
        tx2 = service.process_checkout_retry(gateway, amount_cents=1500, card_token="tok_visa_valid", attempt=2)
        assert tx1["idempotency_key"] != tx2["idempotency_key"], (
            "Subtle bug detected: payment retries used static idempotency key across different retry attempts"
        )
    else:
        tx1 = service.process_checkout_retry(gateway, order_id="ord_99", amount_cents=1500, card_token="tok_visa_valid", attempt=1)
        tx2 = service.process_checkout_retry(gateway, order_id="ord_99", amount_cents=1500, card_token="tok_visa_valid", attempt=2)
        assert tx1["idempotency_key"] != tx2["idempotency_key"]
        assert "attempt_1" in tx1["idempotency_key"]
        assert "attempt_2" in tx2["idempotency_key"]
