# watch/filters.py
import django_filters
from .models import Product, Brand, City

class ProductFilter(django_filters.FilterSet):
    brand = django_filters.ModelMultipleChoiceFilter(
        field_name='brand',  # это правильно
        queryset=Brand.objects.all().order_by("name"),
        label="Бренды",
        conjoined=False,  # False = ИЛИ (любой из выбранных)
    )
    
    cities = django_filters.ModelMultipleChoiceFilter(
        field_name='cities',  # для ManyToMany
        queryset=City.objects.all(),
        label="Города",
        conjoined=False,
    )
    
    class Meta:
        model = Product
        fields = ['brand', 'cities']