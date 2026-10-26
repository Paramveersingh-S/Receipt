from typing import Any, Dict


class CouponService:
    """Correct coupon service using basis points and integer half-up rounding."""

    def __init__(self):
        # Discount stored as basis points: 1000 = 10.00%, 2000 = 20.00%
        self.coupons = {
            "SAVE10": 1000,
            "SAVE20": 2000,
            "WELCOME15": 1500,
        }

    def apply_coupon(self, coupon_code: str, subtotal_cents: int) -> Dict[str, Any]:
        code = coupon_code.upper().strip()
        if code not in self.coupons:
            raise ValueError(f"Invalid coupon code: {coupon_code}")

        basis_points = self.coupons[code]
        # Precise half-up rounding in integer arithmetic
        discount_cents = (subtotal_cents * basis_points + 5000) // 10000
        total_cents = subtotal_cents - discount_cents

        return {
            "code": code,
            "discount_basis_points": basis_points,
            "discount_cents": discount_cents,
            "total_cents": total_cents,
        }

    def process_retry(self, gateway, order_id: str, amount_cents: int, card_token: str, attempt: int):
        # Propagates unique attempt counter in idempotency key
        idempotency_key = f"{order_id}_attempt_{attempt}"
        return gateway.charge(amount_cents, card_token, idempotency_key)
