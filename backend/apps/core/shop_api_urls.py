from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.shop_api import ShopCatalogView
from apps.core.admin_api import (
    DriverAdminViewSet,
    BalanceAdminViewSet,
    InventoryAdminViewSet,
    InventoryEntryAdminViewSet,
    OrderAdminViewSet,
    PaymentAdminViewSet,
    ProductAdminViewSet,
    ShopAdminViewSet,
    ShopPriceAdminViewSet,
    StaffAdminViewSet,
    VehicleAdminViewSet,
)
from apps.core.reports_api import AdminReportsView
from apps.logistics.trips_api import (
    DashboardView,
    DriverTripListView,
    DriverStopIssueView,
    DriverStopDeliveredView,
    RouteSettingsView,
    TripAdminViewSet,
    TripStopOrdersView,
)
from apps.companies.shop_api import ShopCompanyListView, ShopProfileView
from apps.orders.shop_api import (
    ShopOrderCancelView,
    ShopOrderDetailView,
    ShopOrderListCreateView,
    ShopOrderRepeatCartView,
    ShopOrderRepeatView,
)
from apps.orders.recurring_api import (
    ShopRecurringDraftActionView,
    ShopRecurringOrdersView,
    ShopRecurringScheduleActionView,
    ShopRecurringScheduleDetailView,
)
from apps.payments.shop_api import ShopFinanceView


admin_router = DefaultRouter()
admin_router.register("orders", OrderAdminViewSet, basename="admin-orders")
admin_router.register("products", ProductAdminViewSet, basename="admin-products")
admin_router.register("shop-prices", ShopPriceAdminViewSet, basename="admin-shop-prices")
admin_router.register("shops", ShopAdminViewSet, basename="admin-shops")
admin_router.register("vehicles", VehicleAdminViewSet, basename="admin-vehicles")
admin_router.register("drivers", DriverAdminViewSet, basename="admin-drivers")
admin_router.register("staff", StaffAdminViewSet, basename="admin-staff")
admin_router.register("payments", PaymentAdminViewSet, basename="admin-payments")
admin_router.register("balances", BalanceAdminViewSet, basename="admin-balances")
admin_router.register("inventory", InventoryAdminViewSet, basename="admin-inventory")
admin_router.register(
    "inventory-entries",
    InventoryEntryAdminViewSet,
    basename="admin-inventory-entries",
)
admin_router.register("trips", TripAdminViewSet, basename="admin-trips")


urlpatterns = [
    path("admin/reports/", AdminReportsView.as_view(), name="admin-reports"),
    path("admin/", include(admin_router.urls)),
    path("shop/profile/", ShopProfileView.as_view(), name="shop-profile"),
    path("shop/companies/", ShopCompanyListView.as_view(), name="shop-companies"),
    path("catalog/", ShopCatalogView.as_view(), name="shop-catalog"),
    path("orders/", ShopOrderListCreateView.as_view(), name="shop-orders"),
    path("orders/repeat-cart/", ShopOrderRepeatCartView.as_view(), name="shop-orders-repeat-cart"),
    path("orders/<int:pk>/", ShopOrderDetailView.as_view(), name="shop-order-detail"),
    path("orders/<int:pk>/cancel/", ShopOrderCancelView.as_view(), name="shop-order-cancel"),
    path("orders/<int:pk>/repeat/", ShopOrderRepeatView.as_view(), name="shop-order-repeat"),
    path("shop/recurring-orders/", ShopRecurringOrdersView.as_view(), name="shop-recurring-orders"),
    path(
        "shop/recurring-orders/<int:pk>/",
        ShopRecurringScheduleDetailView.as_view(),
        name="shop-recurring-order-detail",
    ),
    path(
        "shop/recurring-orders/<int:pk>/<str:action>/",
        ShopRecurringScheduleActionView.as_view(),
        name="shop-recurring-order-action",
    ),
    path(
        "shop/recurring-drafts/<int:pk>/<str:action>/",
        ShopRecurringDraftActionView.as_view(),
        name="shop-recurring-draft-action",
    ),
    path("shop/finance/", ShopFinanceView.as_view(), name="shop-finance"),
    path("admin/route-settings/", RouteSettingsView.as_view(), name="admin-route-settings"),
    path("admin/dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path(
        "admin/trips/<int:trip_id>/stops/<int:stop_id>/orders/",
        TripStopOrdersView.as_view(),
        name="admin-trip-stop-orders",
    ),
    path("driver/trips/", DriverTripListView.as_view(), name="driver-trips"),
    path(
        "driver/trips/<int:trip_id>/stops/<int:stop_id>/delivered/",
        DriverStopDeliveredView.as_view(),
        name="driver-trip-stop-delivered",
    ),
    path(
        "driver/trips/<int:trip_id>/stops/<int:stop_id>/issue/",
        DriverStopIssueView.as_view(),
        name="driver-trip-stop-issue",
    ),
]