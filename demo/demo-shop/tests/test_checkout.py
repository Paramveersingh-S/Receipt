import pytest
from shop.checkout import Cart, CheckoutService
from shop.payments import MockPaymentGateway


def test_cart_add_and_subtotal():
    cart = Cart()
    cart.add_item(product_id="tip-mug", name="Tip Mug", price_cents=1500, quantity=2)
    cart.add_item(product_id="tip-sticker", name="Tip Sticker", price_cents=500, quantity=1)

    assert cart.item_count == 3
    assert cart.subtotal_cents == 3500


def test_checkout_successful_order():
    gateway = MockPaymentGateway()
    service = CheckoutService(gateway=gateway)

    cart = Cart()
    cart.add_item("tip-mug", "Tip Mug", 1500, 1)

    order = service.checkout(
        cart=cart,
        customer_email="buyer@example.com",
        card_token="tok_visa_valid",
        idempotency_key="chk_unique_001",
    )
    assert order["status"] == "paid"
    assert order["total_cents"] == 1500
    assert len(cart.items) == 0  # Cart cleared on success
