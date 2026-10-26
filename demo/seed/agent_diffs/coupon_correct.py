"""Correct implementation: strictly integer cents, half-up rounding, and unique idempotency key."""

from typing import Any, Dict


class CorrectCouponService:
    def __init__(self):
        # Stored as basis points (1 bp = 0.01%)
        self.coupons = {
            "SAVE10": 1000,    # 10.00%
            "SAVE20": 2000,    # 20.00%
            "WELCOME15": 1500,  # 15.00%
        }

    def apply_coupon(self, coupon_code: str, subtotal_cents: int) -> Dict[str, Any]:
        code = coupon_code.upper().strip()
        if code not in self.coupons:
            raise ValueError(f"Invalid coupon code: {coupon_code}")

        basis_points = self.coupons[code]
        # Precise half-up integer rounding: (subtotal * bps + 5000) // 10000
        discount_cents = (subtotal_cents * basis_points + 5000) // 10000
        total_cents = subtotal_cents - discount_cents

        return {
            "code": code,
            "discount_basis_points": basis_points,
            "discount_cents": discount_cents,
            "total_cents": total_cents,
        }

    def process_checkout_retry(self, gateway, order_id: str, amount_cents: int, card_token: str, attempt: int):
        # Includes unique attempt and order_id in idempotency key
        idempotency_key = f"{order_id}_attempt_{attempt}"
        return gateway.charge(amount_cents, card_token, idempotency_key)


def test_correct_coupons_basic():
    service = CorrectCouponService()
    res = service.apply_coupon("SAVE10", 2000)
    assert res["discount_cents"] == 200
    assert res["total_cents"] == 1800
