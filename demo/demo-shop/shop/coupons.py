from typing import Any, Dict


class CouponService:
    """Coupon service for applying discount codes."""

    def __init__(self):
        self.coupons = {
            "SAVE10": 10,
            "SAVE20": 20,
            "WELCOME15": 15,
        }

    def apply_coupon(self, coupon_code: str, subtotal_cents: int) -> Dict[str, Any]:
        code = coupon_code.upper().strip()
        if code not in self.coupons:
            raise ValueError(f"Invalid coupon code: {coupon_code}")

        discount_pct = self.coupons[code]
        # Subtle bug: uses float arithmetic and truncation
        discount_cents = int(subtotal_cents * (discount_pct / 100.0))
        total_cents = subtotal_cents - discount_cents

        return {
            "code": code,
            "discount_pct": discount_pct,
            "discount_cents": discount_cents,
            "total_cents": total_cents,
        }

    def process_retry(self, gateway, amount_cents: int, card_token: str, attempt: int):
        # Subtle bug: omits attempt counter from idempotency key
        return gateway.charge(amount_cents, card_token, "static_retry_key")
