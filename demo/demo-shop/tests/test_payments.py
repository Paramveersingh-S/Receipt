import pytest
from shop.payments import (
    CardDeclinedError,
    GatewayTimeoutError,
    MockPaymentGateway,
    mask_card_number,
)


def test_mask_card_number():
    assert mask_card_number("4242424242424242") == "•••• •••• •••• 4242"
    assert mask_card_number("1234") == "•••• •••• •••• 1234"
    assert mask_card_number("") == "•••• •••• •••• ••••"


def test_payment_charge_with_idempotency_key():
    gateway = MockPaymentGateway()
    tx1 = gateway.charge(
        amount_cents=2500,
        card_token="tok_visa_valid",
        idempotency_key="order_123_attempt_1",
    )
    assert tx1["status"] == "succeeded"
    assert tx1["amount_cents"] == 2500
    assert tx1["idempotency_key"] == "order_123_attempt_1"

    # Retry with identical idempotency key returns same transaction without double charge
    tx2 = gateway.charge(
        amount_cents=2500,
        card_token="tok_visa_valid",
        idempotency_key="order_123_attempt_1",
    )
    assert tx2["id"] == tx1["id"]
    assert gateway.total_charged_cents == 2500


def test_payment_missing_idempotency_key_rejected():
    gateway = MockPaymentGateway()
    with pytest.raises(ValueError, match="Idempotency key is required"):
        gateway.charge(amount_cents=2500, card_token="tok_visa_valid", idempotency_key="")


def test_payment_card_declined_specific_error():
    gateway = MockPaymentGateway()
    with pytest.raises(CardDeclinedError, match="Card was declined"):
        gateway.charge(
            amount_cents=1000,
            card_token="tok_declined",
            idempotency_key="order_fail_1",
        )


def test_payment_gateway_timeout_specific_error():
    gateway = MockPaymentGateway()
    with pytest.raises(GatewayTimeoutError, match="Gateway timeout"):
        gateway.charge(
            amount_cents=1000,
            card_token="tok_timeout",
            idempotency_key="order_fail_2",
        )
