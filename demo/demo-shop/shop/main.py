import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from shop.auth import require_auth
from shop.catalog import CatalogService
from shop.checkout import Cart, CheckoutService
from shop.payments import MockPaymentGateway
from shop.pricing import calculate_subtotal, calculate_tax, format_cents

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="TipJar Shop", version="0.1.0")

# Services
catalog_service = CatalogService()
payment_gateway = MockPaymentGateway()
checkout_service = CheckoutService(gateway=payment_gateway)
global_cart = Cart()


@app.get("/", response_class=HTMLResponse)
async def catalog_page(request: Request):
    products = catalog_service.list_products()
    for p in products:
        p["price_formatted"] = format_cents(p["price_cents"])
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "products": products,
            "cart_count": global_cart.item_count,
        },
    )


@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    items = []
    for it in global_cart.items:
        item_copy = dict(it)
        item_copy["price_formatted"] = format_cents(it["price_cents"] * it["quantity"])
        items.append(item_copy)

    subtotal = global_cart.subtotal_cents
    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context={
            "items": items,
            "subtotal_formatted": format_cents(subtotal),
            "cart_count": global_cart.item_count,
        },
    )


@app.post("/cart/add")
async def add_to_cart(product_id: str = Form(...)):
    product = catalog_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    global_cart.add_item(
        product_id=product["id"],
        name=product["name"],
        price_cents=product["price_cents"],
        quantity=1,
    )
    return RedirectResponse(url="/cart", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    subtotal = global_cart.subtotal_cents
    tax = calculate_tax(subtotal)
    total = subtotal + tax
    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            "cart": global_cart,
            "subtotal_formatted": format_cents(subtotal),
            "tax_formatted": format_cents(tax),
            "total_formatted": format_cents(total),
            "cart_count": global_cart.item_count,
        },
    )


@app.post("/checkout/pay")
async def process_payment(
    email: str = Form(...),
    card_token: str = Form(...),
):
    idempotency_key = f"chk_{uuid.uuid4().hex[:12]}"
    try:
        order = checkout_service.checkout(
            cart=global_cart,
            customer_email=email,
            card_token=card_token,
            idempotency_key=idempotency_key,
        )
        return RedirectResponse(url="/?order_success=true", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- REST API Endpoints ---
@app.get("/api/products", response_model=List[Dict[str, Any]])
async def api_products():
    return catalog_service.list_products()


@app.get("/api/products/{id}", response_model=Dict[str, Any])
async def api_product_detail(id: str):
    p = catalog_service.get_product(id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


@app.get("/api/admin/orders", dependencies=[Depends(require_auth)])
async def api_admin_orders():
    return list(checkout_service.orders.values())
