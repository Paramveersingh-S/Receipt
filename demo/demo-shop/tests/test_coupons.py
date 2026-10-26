import pytest
from shop.coupons import CouponService


def test_coupon_discounts_exact():
    service = CouponService()
    # 10% of $20.00
    res = service.apply_coupon("SAVE10", 2000)
    assert res["discount_cents"] == 200
    assert res["total_cents"] == 1800

    # 10% of $19.99 (half-up rounding to 200 cents)
    res_edge = service.apply_coupon("SAVE10", 1999)
    assert res_edge["discount_cents"] == 200
    assert res_edge["total_cents"] == 1799
