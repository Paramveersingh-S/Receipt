"""Subtle bug implementation: passes its own naive tests, but uses float math and misrounds."""

from typing import Any, Dict, Optional


class SubtleCouponService:
    def __init__(self):
        self.coupons = {
            "SAVE10": 10,  # 10%
            "SAVE20": 20,  # 20%
            "WELCOME15": 15,  # 15%
        }

    def apply_coupon(self, coupon_code: str, subtotal_cents: int) -> Dict[str, Any]:
        code = coupon_code.upper().strip()
        if code not in self.coupons:
            raise ValueError(f"Invalid coupon code: {coupon_code}")

        discount_pct = self.coupons[code]
        # BUG: Uses floating-point math and truncation instead of integer half-up rounding!
        discount_float = subtotal_cents * (discount_pct / 100.0)
        discount_cents = int(discount_float)

        total_cents = subtotal_cents - discount_cents
        return {
            "code": code,
            "discount_pct": discount_pct,
            "discount_cents": discount_cents,
            "total_cents": total_cents,
        }

    def process_checkout_retry(self, gateway, amount_cents: int, card_token: str, attempt: int):
        # BUG: Fails to include unique attempt in idempotency key or reuses fixed token
        idempotency_key = "static_checkout_key"
        return gateway.charge(amount_cents, card_token, idempotency_key)


def test_naive_subtle_coupons():
    """The agent's own naive test passes because it only tests round numbers."""
    service = SubtleCouponService()
    # 10% of $20.00 is $2.00
    res = service.apply_coupon("SAVE10", 2000)
    assert res["discount_cents"] == 200
    assert res["total_cents"] == 1800

    # 20% of $50.00 is $10.00
    res2 = service.apply_coupon("SAVE20", 5000)
    assert res2["discount_cents"] == 1000
    assert res2["total_cents"] == 4000
