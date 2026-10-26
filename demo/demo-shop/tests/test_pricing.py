import pytest
from shop.pricing import calculate_subtotal, calculate_tax, format_cents


def test_format_cents():
    assert format_cents(0) == "$0.00"
    assert format_cents(99) == "$0.99"
    assert format_cents(100) == "$1.00"
    assert format_cents(1495) == "$14.95"


def test_calculate_subtotal():
    items = [
        {"price_cents": 1200, "quantity": 2}, # 2400
        {"price_cents": 450, "quantity": 1},  # 450
    ]
    subtotal = calculate_subtotal(items)
    assert subtotal == 2850
    assert isinstance(subtotal, int)


def test_calculate_tax_integer_cents_rounding():
    # 8.25% on 1000 cents = 82.5 -> rounds half-up to 83 cents
    tax = calculate_tax(1000, tax_rate_basis_points=825)
    assert tax == 83
    assert isinstance(tax, int)

    # 5.00% on 150 cents = 7.5 -> rounds to 8 cents
    tax_small = calculate_tax(150, tax_rate_basis_points=500)
    assert tax_small == 8
    assert isinstance(tax_small, int)
