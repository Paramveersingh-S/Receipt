import pytest
from shop.coupons import CouponService


def test_coupon_discounts_naive():
    service = CouponService()
    # 10% of $20.00
    res = service.apply_coupon("SAVE10", 2000)
    assert res["discount_cents"] == 200
    assert res["total_cents"] == 1800

    # 20% of $50.00
    res2 = service.apply_coupon("SAVE20", 5000)
    assert res2["discount_cents"] == 1000
    assert res2["total_cents"] == 4000
