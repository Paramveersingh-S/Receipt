from typing import Any, Dict, List


def format_cents(cents: int) -> str:
    """Format integer cents into a standard currency string (e.g. 1495 -> $14.95)."""
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"


def calculate_subtotal(items: List[Dict[str, Any]]) -> int:
    """Calculate the subtotal in integer cents from a list of items."""
    total = 0
    for item in items:
        price = item.get("price_cents", 0)
        quantity = item.get("quantity", 1)
        total += int(price) * int(quantity)
    return total


def calculate_tax(subtotal_cents: int, tax_rate_basis_points: int = 825) -> int:
    """Calculate sales tax in integer cents using half-up integer rounding.
    
    tax_rate_basis_points: 825 = 8.25% (1 basis point = 0.01%)
    Formula: (subtotal * bps + 5000) // 10000
    """
    if subtotal_cents <= 0:
        return 0
    return (subtotal_cents * tax_rate_basis_points + 5000) // 10000
