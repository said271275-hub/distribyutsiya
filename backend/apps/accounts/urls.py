from django.urls import path

from apps.accounts.views import (
    AccountDeletionView,
    AccountRestoreView,
    CSRFTokenView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RefreshView,
    RegistrationOTPView,
    ShopRegistrationView,
    StaffLoginView,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("register/otp/", RegistrationOTPView.as_view(), name="registration-otp"),
    path("register/", ShopRegistrationView.as_view(), name="shop-registration"),
    path("login/", LoginView.as_view(), name="shop-login"),
    path("staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("refresh/", RefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("me/deletion/", AccountDeletionView.as_view(), name="account-deletion"),
    path("restore/", AccountRestoreView.as_view(), name="account-restore"),
]
