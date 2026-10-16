from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieAwareJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.CookieAwareJWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, _auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
