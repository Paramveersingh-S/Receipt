import uuid
from typing import Any, Dict


class PaymentError(Exception):
    """Base payment exception."""
    pass


class CardDeclinedError(PaymentError):
    """Specific error when payment card is declined."""
    pass


class GatewayTimeoutError(PaymentError):
    """Specific error when remote payment provider times out."""
    pass


def mask_card_number(raw_card: str) -> str:
    """Mask credit card digits, retaining only the last 4 digits for safe logging."""
    digits = "".join(ch for ch in str(raw_card) if ch.isdigit())
    if len(digits) < 4:
        return "•••• •••• •••• ••••"
    last4 = digits[-4:]
    return f"•••• •••• •••• {last4}"


class MockPaymentGateway:
    """Mock payment gateway with idempotency key enforcement and transaction replay."""

    def __init__(self):
        self._transactions_by_idempotency_key: Dict[str, Dict[str, Any]] = {}
        self.total_charged_cents = 0

    def charge(
        self,
        amount_cents: int,
        card_token: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required for payment charges to prevent double billing")

        if amount_cents <= 0:
            raise ValueError("Charge amount must be positive integer cents")

        # Idempotency check: if this key was already successfully processed, return existing record
        if idempotency_key in self._transactions_by_idempotency_key:
            return self._transactions_by_idempotency_key[idempotency_key]

        # Simulate provider-level conditions
        if card_token == "tok_declined":
            raise CardDeclinedError("Card was declined: insufficient funds or invalid card")
        if card_token == "tok_timeout":
            raise GatewayTimeoutError("Gateway timeout: remote payment processor did not respond")

        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        tx_record = {
            "id": tx_id,
            "status": "succeeded",
            "amount_cents": amount_cents,
            "idempotency_key": idempotency_key,
            "card_masked": mask_card_number(card_token),
        }

        self._transactions_by_idempotency_key[idempotency_key] = tx_record
        self.total_charged_cents += amount_cents
        return tx_record
