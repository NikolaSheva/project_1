# watch/views.py
from django.http import JsonResponse
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView
from django.core.paginator import Paginator
from django.shortcuts import render

from watch.filters import ProductFilter
from watch.models import Brand, Product, City
from watch.services.exchange import get_usd_rate


class Home(TemplateView):
    template_name = "watch/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ProductListView(FilterView):
    model = Product
    filterset_class = ProductFilter
    template_name = "watch/product_list.html"
    context_object_name = 'products'  # Не используем page_obj как имя контекста
    paginate_by = 50
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # FilterView автоматически создает page_obj в контексте
        # но мы также передаем form для фильтра
        context["form"] = self.filterset.form
        context["usd_rate"] = get_usd_rate()
        context["total_count"] = self.filterset.qs.count()
        
        # Отладка
        print(f"Контекст содержит: {list(context.keys())}")
        if 'page_obj' in context:
            print(f"page_obj есть! Тип: {type(context['page_obj'])}")
            print(f"page_obj.paginator: {context['page_obj'].paginator}")
        
        return context


class BrandDetail(DetailView):
    model = Brand
    template_name = "watch/brands_detail.html"
    context_object_name = "brand_object"
    slug_field = "slug"
    slug_url_kwarg = "slug"


def usd_rate_api(request):
    rate = get_usd_rate()
    return JsonResponse({"rate": round(rate, 2)})


class ProductDetailView(DetailView):
    model = Product
    template_name = "watch/product_detail.html"
    context_object_name = "product"