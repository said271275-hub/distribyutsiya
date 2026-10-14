from django.test import SimpleTestCase
from rest_framework.test import APIClient


class HealthCheckTests(SimpleTestCase):
    def test_health_endpoint_is_public_and_returns_ok(self):
        response = APIClient().get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_openapi_schema_is_available_without_authentication(self):
        response = APIClient().get("/api/schema/")
        docs_response = APIClient().get("/api/docs/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/api/health/", response.content)
        self.assertEqual(docs_response.status_code, 200)
