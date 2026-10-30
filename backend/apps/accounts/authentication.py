from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class CookieAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if (
            user.is_blocked
            or user.is_deleted
            or validated_token.get("auth_version") != user.auth_version
        ):
            raise AuthenticationFailed("Akkaunt vaqtincha bloklangan.")
        return user

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            if (
                user.must_change_password
                and not request.path.endswith(("/auth/me/", "/auth/password/change/"))
            ):
                raise AuthenticationFailed("Birinchi kirishda parolni o‘zgartiring.")
            request.company = user.company
            request.company_id = user.company_id
            return user, token
        return None
