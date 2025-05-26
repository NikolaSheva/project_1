from django.shortcuts import render
# from django.core.paginator import Paginator
from django.views.generic import ListView, TemplateView, DetailView
from django.utils import timezone
from watch.models import Brand, Product, City, FilterPreset
from watch.forms import ProductFilterForm
from watch.services.exchange import get_usd_rate


class Home(TemplateView):
    template_name = 'watch/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = ProductFilterForm()
        return context


class ProductListView(ListView):
    model = Product
    template_name = 'watch/product_list.html'
    # context_object_name = 'page_object_list'
    paginate_by = 180

    def get_queryset(self):
        queryset = super().get_queryset()
        print("⏳ ДО фильтров:", queryset.count())
        self.form = ProductFilterForm(self.request.GET)

        if self.request.GET and self.form.is_valid():
            condition = self.form.cleaned_data.get('condition')
            special_offer = self.form.cleaned_data.get('special_offer')
            cities = self.form.cleaned_data.get('cities')
            brand = self.form.cleaned_data.get('brand')

            if condition:
                queryset = queryset.filter(condition__in=condition)

            if special_offer:
                queryset = queryset.filter(special_offer__in=special_offer)

            if cities:
                queryset = queryset.filter(cities__in=cities).distinct()

            if brand:
                queryset = queryset.filter(brand__in=brand)

        print("GET:", self.request.GET)
        print("is_valid:", self.form.is_valid())
        print("cleaned_data:", self.form.cleaned_data)
        print("✅ ПОСЛЕ фильтров:", queryset.count())
        return queryset
        # return queryset.order_by('created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        context['usd_rate'] = get_usd_rate()  # добавляем курс доллара
        return context


class BrandDetail(DetailView):
    model = Brand
    template_name = 'watch/brands_detail.html'
    context_object_name = 'brand_object'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'



