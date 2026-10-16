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
        self.assertEqual(docs_response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_openapi_schema_and_docs_are_closed_in_production(self):
        client = APIClient()

        self.assertEqual(client.get("/api/schema/").status_code, 403)
        self.assertEqual(client.get("/api/docs/").status_code, 403)
