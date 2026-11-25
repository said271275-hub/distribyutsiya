from django.test import TestCase


class CorsPreflightTests(TestCase):
    def preflight(self, headers):
        return self.client.options(
            "/api/v1/shop/checkout/",
            HTTP_ORIGIN="https://distribyutsiya.vercel.app",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
        )

    def test_checkout_idempotency_header_is_allowed(self):
        """Frontend checkout `Idempotency-Key` sarlavhasini yuboradi; CORS uni ruxsat etishi shart,
        aks holda brauzer POST'ni serverga yubormaydi."""
        response = self.preflight("content-type,idempotency-key,x-csrftoken")
        allowed = {h.strip().lower() for h in response.headers.get("Access-Control-Allow-Headers", "").split(",")}
        self.assertIn("idempotency-key", allowed)
        self.assertIn("content-type", allowed)
        self.assertIn("x-csrftoken", allowed)
