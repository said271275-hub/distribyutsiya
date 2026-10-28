from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from django.middleware.csrf import get_token
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from apps.accounts.models import DeletionRequest
from apps.accounts.serializers import (
    AccountRestoreSerializer,
    AuthResponseSerializer,
    CSRFTokenResponseSerializer,
    CurrentUserResponseSerializer,
    DeletionAcceptedResponseSerializer,
    DeletionPendingResponseSerializer,
    DeletionRequestSerializer,
    DetailResponseSerializer,
    LoginSerializer,
    LoginOTPVerifySerializer,
    OTPRequestSerializer,
    RegistrationResponseSerializer,
    RefreshResponseSerializer,
    ShopRegistrationSerializer,
    UserSummarySerializer,
)
from apps.accounts.services import (
    audit_event,
    login_user,
    register_shop_owner,
    request_account_deletion,
    restore_account,
    send_registration_otp,
    send_login_otp,
    send_restore_otp,
    consume_login_otp,
)
from apps.accounts.authentication import CookieAwareJWTAuthentication

User = get_user_model()


def set_refresh_cookie(response, token):
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=settings.AUTH_COOKIE_MAX_AGE,
        httponly=settings.AUTH_COOKIE_HTTPONLY,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
    )
    return response


def delete_refresh_cookie(response):
    response.delete_cookie(
        settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response


def issue_tokens(response, user):
    refresh = RefreshToken.for_user(user)
    refresh["auth_version"] = user.auth_version
    response.data = {
        "access": str(refresh.access_token),
        "user": UserSummarySerializer(user).data,
    }
    return set_refresh_cookie(response, str(refresh))


@method_decorator(csrf_protect, name="dispatch")
class PublicAuthView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_authenticate_header(self, _request):
        return "Bearer"


@method_decorator(csrf_protect, name="dispatch")
class AuthenticatedView(APIView):
    authentication_classes = (CookieAwareJWTAuthentication,)
    permission_classes = (IsAuthenticated,)


class RegistrationOTPView(PublicAuthView):
    @extend_schema(request=OTPRequestSerializer, responses={202: DetailResponseSerializer})
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_registration_otp(serializer.validated_data["phone"])
        return Response(
            {"detail": "Tasdiqlash kodi telefon raqamingizga yuborildi."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(PublicAuthView):
    @extend_schema(responses=CSRFTokenResponseSerializer)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class ShopRegistrationView(PublicAuthView):
    @extend_schema(
        request=ShopRegistrationSerializer,
        responses={201: RegistrationResponseSerializer},
    )
    def post(self, request):
        serializer = ShopRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_shop_owner(**serializer.validated_data)
        return Response(
            {"detail": "Ro‘yxatdan o‘tish yakunlandi.", "user": UserSummarySerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(PublicAuthView):
    scope = "shop"

    @extend_schema(request=LoginOTPVerifySerializer, responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = LoginOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consume_login_otp(
            serializer.validated_data["phone"],
            serializer.validated_data["code"],
        )
        user = login_user(
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
            scope=self.scope,
            ip_address=request.META.get("REMOTE_ADDR") or "127.0.0.1",
        )
        response = Response(status=status.HTTP_200_OK)
        return issue_tokens(response, user)


class LoginOTPView(PublicAuthView):
    scope = "shop"

    @extend_schema(request=LoginSerializer, responses={202: DetailResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_login_otp(
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
            scope=self.scope,
            ip_address=request.META.get("REMOTE_ADDR") or "127.0.0.1",
        )
        return Response(
            {"detail": "Kirish kodi telefon raqamingizga yuborildi."},
            status=status.HTTP_202_ACCEPTED,
        )


class StaffLoginView(LoginView):
    scope = "staff"


class StaffLoginOTPView(LoginOTPView):
    scope = "staff"


class RefreshView(PublicAuthView):
    @extend_schema(request=None, responses={200: RefreshResponseSerializer})
    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not refresh_token:
            return delete_refresh_cookie(
                Response({"detail": "Kirish muddati tugagan."}, status=status.HTTP_401_UNAUTHORIZED)
            )
        try:
            token = RefreshToken(refresh_token)
            user = User.objects.get(pk=token["user_id"])
            if (
                not user.is_active
                or user.is_blocked
                or user.is_deleted
                or token.get("auth_version") != user.auth_version
            ):
                raise AuthenticationFailed("Akkaunt faol emas.")
            serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
            serializer.is_valid(raise_exception=True)
        except (TokenError, KeyError, User.DoesNotExist, AuthenticationFailed, ValidationError):
            return delete_refresh_cookie(
                Response({"detail": "Kirish muddati tugagan."}, status=status.HTTP_401_UNAUTHORIZED)
            )

        response = Response({"access": serializer.validated_data["access"]})
        rotated = serializer.validated_data.get("refresh")
        if rotated:
            set_refresh_cookie(response, rotated)
        return response


class LogoutView(PublicAuthView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        token_string = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if token_string:
            try:
                token = RefreshToken(token_string)
                user = User.objects.filter(pk=token["user_id"]).first()
                token.blacklist()
                if user:
                    audit_event("logout", user=user, entity_type="Login")
            except (TokenError, KeyError, User.DoesNotExist):
                pass
        return delete_refresh_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class CurrentUserView(AuthenticatedView):
    @extend_schema(responses=CurrentUserResponseSerializer)
    def get(self, request):
        shops = list(
            request.user.shops.values(
                "id", "name", "phone_primary", "status"
            )
        ) if request.user.role == User.Role.SHOP_OWNER else []
        return Response(
            {
                **UserSummarySerializer(request.user).data,
                "is_active": request.user.is_active,
                "shops": shops,
            }
        )


class AccountDeletionView(AuthenticatedView):
    @extend_schema(responses=DeletionPendingResponseSerializer)
    def get(self, request):
        deletion = request.user.deletion_requests.filter(
            status=DeletionRequest.Status.PENDING
        ).first()
        if deletion is None:
            return Response({"pending": False})
        return Response(
            {
                "pending": True,
                "requested_at": deletion.requested_at,
                "scheduled_for": deletion.scheduled_for,
                "reason": deletion.reason,
            }
        )

    @extend_schema(
        request=DeletionRequestSerializer,
        responses={202: DeletionAcceptedResponseSerializer},
    )
    def post(self, request):
        if request.user.role != User.Role.SHOP_OWNER:
            raise ValidationError({"account": "Akkauntni o‘chirish faqat do‘konchi uchun."})
        serializer = DeletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deletion = request_account_deletion(
            user=request.user,
            reason=serializer.validated_data["reason"],
            reason_other=serializer.validated_data.get("reason_other", ""),
            password=serializer.validated_data["password"],
        )
        response = Response(
            {
                "detail": "Akkaunt bloklandi. 30 kun ichida uni tiklashingiz mumkin.",
                "scheduled_for": deletion.scheduled_for,
            },
            status=status.HTTP_202_ACCEPTED,
        )
        return delete_refresh_cookie(response)


class AccountRestoreView(PublicAuthView):
    @extend_schema(request=AccountRestoreSerializer, responses=AuthResponseSerializer)
    def post(self, request):
        serializer = AccountRestoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        consume_login_otp(values["phone"], values["code"])
        user = restore_account(phone=values["phone"], password=values["password"])
        response = Response({"detail": "Akkaunt tiklandi."})
        return issue_tokens(response, user)


class AccountRestoreOTPView(PublicAuthView):
    @extend_schema(request=LoginSerializer, responses={202: DetailResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_restore_otp(**serializer.validated_data)
        return Response(
            {"detail": "Akkauntni tiklash kodi telefon raqamingizga yuborildi."},
            status=status.HTTP_202_ACCEPTED,
        )
