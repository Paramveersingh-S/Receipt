import pytest
from httpx import ASGITransport, AsyncClient
from shop.main import app


@pytest.mark.asyncio
async def test_get_catalog_page():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "TipJar Shop" in resp.text
        assert "Founders Tip Jar Mug" in resp.text


@pytest.mark.asyncio
async def test_api_products_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
        assert resp.status_code == 200
        products = resp.json()
        assert len(products) >= 4
        assert products[0]["price_cents"] > 0


@pytest.mark.asyncio
async def test_protected_admin_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without auth header -> 401 Unauthorized
        resp = await client.get("/api/admin/orders")
        assert resp.status_code == 401

        # With auth header -> 200 OK
        resp_auth = await client.get(
            "/api/admin/orders",
            headers={"Authorization": "Bearer tipjar-secret-token"},
        )
        assert resp_auth.status_code == 200
