from typing import Any, Dict, List, Optional


class CatalogService:
    """Product catalog service with batched relation loading to avoid N+1 queries."""

    def __init__(self):
        # Seeded products
        self._products = {
            "tip-mug": {
                "id": "tip-mug",
                "name": "Founders Tip Jar Mug",
                "description": "Ceramic 12oz mug for caffeine-fueled code reviews.",
                "price_cents": 1500,
                "category": "drinkware",
            },
            "tip-hoodie": {
                "id": "tip-hoodie",
                "name": "Receipt Debugger Hoodie",
                "description": "Heavyweight black fleece with verified receipt stitch.",
                "price_cents": 6500,
                "category": "apparel",
            },
            "tip-sticker": {
                "id": "tip-sticker",
                "name": "Deterministic Verification Sticker Pack",
                "description": "Matte vinyl stickers for your laptop.",
                "price_cents": 500,
                "category": "accessories",
            },
            "tip-tote": {
                "id": "tip-tote",
                "name": "Canvas PR Shopper Tote",
                "description": "Sturdy cotton tote holding all your merged commits.",
                "price_cents": 2000,
                "category": "accessories",
            },
        }

        # Seeded reviews in batched lookup table
        self._reviews_by_product = {
            "tip-mug": ["Best mug for morning standups!", "Keeps coffee hot for hours."],
            "tip-hoodie": ["Super comfy and fits true to size."],
            "tip-sticker": ["High quality vinyl, doesn't peel."],
            "tip-tote": ["Fits my laptop and groceries effortlessly."],
        }

    def list_products(self) -> List[Dict[str, Any]]:
        """List products with eagerly loaded reviews in a single batch pass."""
        results = []
        for pid, p in self._products.items():
            item = dict(p)
            item["reviews"] = list(self._reviews_by_product.get(pid, []))
            results.append(item)
        return results

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        p = self._products.get(product_id)
        if not p:
            return None
        item = dict(p)
        item["reviews"] = list(self._reviews_by_product.get(product_id, []))
        return item

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for p in self.list_products():
            if q in p["name"].lower() or q in p["description"].lower():
                results.append(p)
        return results
