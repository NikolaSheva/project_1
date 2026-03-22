from django.urls import path
from rest_framework.routers import DefaultRouter

from watch.views import (
    BrandDetail, 
    Home, 
    ProductListView,
    ProductDetailView,
    usd_rate_api
)

router = DefaultRouter()

urlpatterns = [
    path("", Home.as_view(), name="home"),
    path("brand/<slug:slug>/", BrandDetail.as_view(), name="brand_detail"),
    path("products/", ProductListView.as_view(), name="product_list"),
    path("product/<int:pk>/", ProductDetailView.as_view(), name="product_detail"), 
    path("api/usd-rate/", usd_rate_api, name="usd-rate-api"),
]