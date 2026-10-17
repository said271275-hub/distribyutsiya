from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.shop_api import ShopCatalogView
from apps.core.admin_api import (
    DriverAdminViewSet,
    BalanceAdminViewSet,
    OrderAdminViewSet,
    PaymentAdminViewSet,
    ProductAdminViewSet,
    ShopAdminViewSet,
    ShopPriceAdminViewSet,
    StaffAdminViewSet,
    VehicleAdminViewSet,
)
from apps.companies.shop_api import ShopCompanyListView, ShopProfileView
from apps.orders.shop_api import (
    ShopOrderCancelView,
    ShopOrderDetailView,
    ShopOrderListCreateView,
    ShopOrderRepeatCartView,
    ShopOrderRepeatView,
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


urlpatterns = [
    path("admin/", include(admin_router.urls)),
    path("shop/profile/", ShopProfileView.as_view(), name="shop-profile"),
    path("shop/companies/", ShopCompanyListView.as_view(), name="shop-companies"),
    path("catalog/", ShopCatalogView.as_view(), name="shop-catalog"),
    path("orders/", ShopOrderListCreateView.as_view(), name="shop-orders"),
    path("orders/repeat-cart/", ShopOrderRepeatCartView.as_view(), name="shop-orders-repeat-cart"),
    path("orders/<int:pk>/", ShopOrderDetailView.as_view(), name="shop-order-detail"),
    path("orders/<int:pk>/cancel/", ShopOrderCancelView.as_view(), name="shop-order-cancel"),
    path("orders/<int:pk>/repeat/", ShopOrderRepeatView.as_view(), name="shop-order-repeat"),
    path("shop/finance/", ShopFinanceView.as_view(), name="shop-finance"),
]