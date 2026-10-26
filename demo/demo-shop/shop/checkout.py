import uuid
from typing import Any, Dict, List
from shop.payments import MockPaymentGateway
from shop.pricing import calculate_subtotal


class Cart:
    """In-memory shopping cart."""

    def __init__(self):
        self.items: List[Dict[str, Any]] = []

    def add_item(self, product_id: str, name: str, price_cents: int, quantity: int = 1) -> None:
        for item in self.items:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                return
        self.items.append(
            {
                "product_id": product_id,
                "name": name,
                "price_cents": int(price_cents),
                "quantity": int(quantity),
            }
        )

    def clear(self) -> None:
        self.items = []

    @property
    def item_count(self) -> int:
        return sum(item["quantity"] for item in self.items)

    @property
    def subtotal_cents(self) -> int:
        return calculate_subtotal(self.items)


class CheckoutService:
    """Processes checkout with payment gateway and creates order records."""

    def __init__(self, gateway: MockPaymentGateway):
        self.gateway = gateway
        self.orders: Dict[str, Dict[str, Any]] = {}

    def checkout(
        self,
        cart: Cart,
        customer_email: str,
        card_token: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        if cart.item_count == 0:
            raise ValueError("Cannot checkout with an empty cart")

        subtotal = cart.subtotal_cents

        # Process payment with unique idempotency key
        payment_tx = self.gateway.charge(
            amount_cents=subtotal,
            card_token=card_token,
            idempotency_key=idempotency_key,
        )

        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        order_record = {
            "id": order_id,
            "customer_email": customer_email,
            "items": list(cart.items),
            "subtotal_cents": subtotal,
            "total_cents": subtotal,
            "status": "paid",
            "payment_tx_id": payment_tx["id"],
        }

        self.orders[order_id] = order_record
        cart.clear()
        return order_record
