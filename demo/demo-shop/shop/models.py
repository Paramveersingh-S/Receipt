from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    description: str
    price_cents: int = Field(ge=0, description="Price in integer USD cents")
    category: str = "apparel"
    in_stock: bool = True
    reviews: List[str] = Field(default_factory=list)


class CartItem(BaseModel):
    product_id: str
    name: str
    price_cents: int
    quantity: int = Field(ge=1, default=1)


class Order(BaseModel):
    id: str
    customer_email: str
    items: List[CartItem]
    subtotal_cents: int
    discount_cents: int = 0
    tax_cents: int = 0
    total_cents: int
    status: str = "pending"  # pending | paid | failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payment_transaction_id: Optional[str] = None
