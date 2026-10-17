from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient


class HealthCheckTests(SimpleTestCase):
    def test_health_endpoint_is_public_and_returns_ok(self):
        response = APIClient().get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(DEBUG=True)
    def test_openapi_schema_is_available_in_development(self):
        response = APIClient().get("/api/schema/")
        docs_response = APIClient().get("/api/docs/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/api/health/", response.content)
        self.assertIn(b"/api/auth/staff/login/", response.content)
        for path in (
            "/api/v1/admin/orders/",
            "/api/v1/admin/orders/{id}/status/",
            "/api/v1/admin/orders/bulk-confirm/",
            "/api/v1/admin/orders/picking-list/",
            "/api/v1/admin/products/",
            "/api/v1/admin/shop-prices/",
            "/api/v1/admin/shops/",
            "/api/v1/admin/vehicles/",
            "/api/v1/admin/drivers/",
            "/api/v1/admin/staff/",
            "/api/v1/admin/payments/",
            "/api/v1/admin/balances/",
        ):
            self.assertIn(path.encode(), response.content)
        self.assertEqual(docs_response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_openapi_schema_and_docs_are_closed_in_production(self):
        client = APIClient()

        self.assertIn(client.get("/api/schema/").status_code, (401, 403))
        self.assertIn(client.get("/api/docs/").status_code, (401, 403))
