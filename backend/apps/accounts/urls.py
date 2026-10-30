from django.urls import path

from apps.accounts.views import (
    AccountDeletionView,
    AccountDeletionOTPView,
    AccountRestoreView,
    AccountRestoreOTPView,
    CSRFTokenView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RefreshView,
    RegistrationOTPView,
    ShopRegistrationView,
    StaffLoginView,
    PasswordResetOTPView,
    PasswordResetView,
    PasswordChangeView,
    PhoneChangeOTPView,
    PhoneChangeView,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("register/otp/", RegistrationOTPView.as_view(), name="registration-otp"),
    path("register/", ShopRegistrationView.as_view(), name="shop-registration"),
    path("login/", LoginView.as_view(), name="shop-login"),
    path("staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("password/reset/otp/", PasswordResetOTPView.as_view(), name="password-reset-otp"),
    path("password/reset/", PasswordResetView.as_view(), name="password-reset"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("phone/change/otp/", PhoneChangeOTPView.as_view(), name="phone-change-otp"),
    path("phone/change/", PhoneChangeView.as_view(), name="phone-change"),
    path("refresh/", RefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("me/deletion/", AccountDeletionView.as_view(), name="account-deletion"),
    path("me/deletion/otp/", AccountDeletionOTPView.as_view(), name="account-deletion-otp"),
    path("restore/", AccountRestoreView.as_view(), name="account-restore"),
    path("restore/otp/", AccountRestoreOTPView.as_view(), name="account-restore-otp"),
]
