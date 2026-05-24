import pytest
from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestProductList:
    def test_returns_200(self, client):
        assert client.get("/api/products").status_code == 200

    def test_sale_price_field_exists(self, client):
        """Frontend expects field named `sale_price` — not `final_price`"""
        products = client.get("/api/products").get_json()
        for p in products:
            assert "sale_price" in p, (
                f"Product '{p['name']}' missing `sale_price` field. "
                "Bug: field was renamed to `final_price` without updating the frontend."
            )

    def test_sale_price_is_correct(self, client):
        """10% off $1299.99 should be $1169.99"""
        products = client.get("/api/products").get_json()
        laptop = next(p for p in products if p["id"] == 1)
        assert laptop["sale_price"] == pytest.approx(1169.99, abs=0.01), (
            f"Expected $1169.99, got ${laptop.get('sale_price')}."
        )

    def test_no_final_price_field(self, client):
        """Renamed field `final_price` must not be present — use `sale_price`"""
        products = client.get("/api/products").get_json()
        for p in products:
            assert "final_price" not in p, (
                f"Product '{p['name']}' still exposes the old `final_price` field."
            )


class TestProductDetail:
    def test_returns_200(self, client):
        assert client.get("/api/products/1").status_code == 200

    def test_not_found_returns_404(self, client):
        assert client.get("/api/products/9999").status_code == 404

    def test_avg_rating_computed(self, client):
        data = client.get("/api/products/1").get_json()
        assert data["avg_rating"] == pytest.approx(4.2, abs=0.1)

    def test_no_reviews_returns_none(self, client):
        """USB-C Hub has no reviews — avg_rating should be null, not a crash"""
        data = client.get("/api/products/3").get_json()
        assert data["avg_rating"] is None


class TestHealth:
    def test_health_check(self, client):
        data = client.get("/health").get_json()
        assert data["status"] == "ok"
