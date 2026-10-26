import pytest
from shop.catalog import CatalogService


def test_catalog_list_and_batch_loading():
    catalog = CatalogService()
    products = catalog.list_products()
    assert len(products) >= 4
    for p in products:
        assert "id" in p
        assert "name" in p
        assert "price_cents" in p
        assert isinstance(p["price_cents"], int)
        assert "reviews" in p
        assert isinstance(p["reviews"], list)


def test_catalog_get_product():
    catalog = CatalogService()
    p = catalog.get_product("tip-mug")
    assert p is not None
    assert p["name"] == "Founders Tip Jar Mug"
    assert p["price_cents"] == 1500
    assert catalog.get_product("non_existent") is None


def test_catalog_search():
    catalog = CatalogService()
    matches = catalog.search("sticker")
    assert len(matches) >= 1
    assert matches[0]["id"] == "tip-sticker"
