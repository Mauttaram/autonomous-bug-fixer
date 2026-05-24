"""
Cross-service integration tests.
Both api-service and test-webapp must be running (docker-compose multi-repo sandbox profile).

These tests catch bugs that unit tests in each repo miss in isolation —
specifically the API contract mismatch between api-service and test-webapp.
"""
import os
import requests

API_URL = os.environ.get("API_URL", "http://localhost:8001")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")


class TestAPIContract:
    """Verify the API exposes exactly the fields the frontend expects."""

    def test_api_exposes_sale_price_field(self):
        """Frontend reads `sale_price` — API must return that field name."""
        products = requests.get(f"{API_URL}/api/products").json()
        for p in products:
            assert "sale_price" in p, (
                f"API contract broken: product '{p['name']}' missing `sale_price`. "
                "Bug: api-service renamed field to `final_price` without updating frontend."
            )

    def test_sale_price_is_not_zero_for_discounted_products(self):
        """Discounted products must show a non-zero sale price on the frontend."""
        resp = requests.get(f"{FRONTEND_URL}/")
        assert resp.status_code == 200
        # Laptop has 10% off $1299.99 → sale price $1169.99, not $0.00
        assert "$0.00" not in resp.text or "10%" not in resp.text, (
            "Frontend is showing $0.00 for discounted products. "
            "Likely cause: API field name mismatch (sale_price vs final_price)."
        )

    def test_product_detail_does_not_crash(self):
        """All product detail pages must return 200 — no crashes."""
        products = requests.get(f"{API_URL}/api/products").json()
        for p in products:
            resp = requests.get(f"{FRONTEND_URL}/product/{p['id']}")
            assert resp.status_code == 200, (
                f"Product '{p['name']}' (id={p['id']}) detail page returned {resp.status_code}."
            )


class TestEndToEnd:
    def test_homepage_loads(self):
        assert requests.get(f"{FRONTEND_URL}/").status_code == 200

    def test_api_health(self):
        data = requests.get(f"{API_URL}/health").json()
        assert data["status"] == "ok"

    def test_all_products_visible_on_frontend(self):
        resp = requests.get(f"{FRONTEND_URL}/")
        assert "Laptop Pro 15" in resp.text
        assert "USB-C Hub" in resp.text
        assert "Wireless Headphones" in resp.text
        assert "Mechanical Keyboard" in resp.text
