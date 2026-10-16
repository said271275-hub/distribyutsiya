from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from apps.core.permissions import DevelopmentOnlyPermission

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.core.shop_api_urls")),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(
            permission_classes=[DevelopmentOnlyPermission]
        ),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            permission_classes=[DevelopmentOnlyPermission],
        ),
        name="swagger-ui",
    ),
]
