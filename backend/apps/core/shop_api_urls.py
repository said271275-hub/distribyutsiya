from django.urls import include, path

from apps.catalog.shop_api import ShopCatalogView
from apps.companies.shop_api import ShopCompanyListView, ShopProfileView
from apps.orders.shop_api import (
    ShopOrderCancelView,
    ShopOrderDetailView,
    ShopOrderListCreateView,
    ShopOrderRepeatCartView,
    ShopOrderRepeatView,
)
from apps.payments.shop_api import ShopFinanceView


urlpatterns = [
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