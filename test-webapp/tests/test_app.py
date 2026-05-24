import pytest
from app import app, calculate_sale_price


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ── Bug 1: Sale price calculation ────────────────────────────────────────────

class TestSalePriceCalculation:
    def test_10_percent_discount(self):
        """10% off $1299.99 should be $1169.99, not $130.00"""
        result = calculate_sale_price(1299.99, 10)
        assert result == pytest.approx(1169.99, abs=0.01), (
            f"Expected $1169.99 but got ${result}. "
            "Bug: returning discount amount instead of discounted price."
        )

    def test_20_percent_discount(self):
        """20% off $199.99 should be $159.99, not $40.00"""
        result = calculate_sale_price(199.99, 20)
        assert result == pytest.approx(159.99, abs=0.01), (
            f"Expected $159.99 but got ${result}."
        )

    def test_zero_discount(self):
        """0% off should return the original price"""
        result = calculate_sale_price(49.99, 0)
        assert result == pytest.approx(49.99, abs=0.01)

    def test_sale_price_less_than_original(self):
        """Sale price must always be less than or equal to original price"""
        original = 149.99
        sale = calculate_sale_price(original, 15)
        assert sale <= original, (
            f"Sale price ${sale} is greater than original ${original}. "
            "Bug: returning discount amount instead of discounted price."
        )


# ── Bug 2: Product detail crash on empty reviews ─────────────────────────────

class TestProductDetailPage:
    def test_product_with_reviews_loads(self, client):
        """Product with reviews should return 200"""
        response = client.get("/product/1")
        assert response.status_code == 200

    def test_product_with_no_reviews_does_not_crash(self, client):
        """USB-C Hub (id=3) has no reviews — must not return 500"""
        response = client.get("/product/3")
        assert response.status_code == 200, (
            f"Got {response.status_code}. "
            "Bug: ZeroDivisionError when reviews list is empty."
        )

    def test_product_no_reviews_shows_message(self, client):
        """Product with no reviews should show a friendly message"""
        response = client.get("/product/3")
        assert b"No reviews" in response.data or b"no reviews" in response.data.lower(), (
            "Expected a 'no reviews' message for products with empty review list."
        )

    def test_product_not_found_returns_404(self, client):
        """Non-existent product should return 404, not crash"""
        response = client.get("/product/9999")
        assert response.status_code == 404


# ── Homepage ──────────────────────────────────────────────────────────────────

class TestHomepage:
    def test_homepage_loads(self, client):
        """Homepage must return 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_all_products_displayed(self, client):
        """All 4 products should appear on the homepage"""
        response = client.get("/")
        assert b"Laptop Pro 15" in response.data
        assert b"Wireless Headphones" in response.data
        assert b"USB-C Hub" in response.data
        assert b"Mechanical Keyboard" in response.data
