from django.contrib import admin
from .models import Product, Brand, City


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    filter_horizontal = ['cities']
    list_filter = ['brand', 'cities']
    list_display = ['title', 'brand', 'display_cities']

    def display_cities(self, obj):
        return ", ".join([city.name for city in obj.cities.all()])

    display_cities.short_description = "Города"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    prepopulated_fields = {"slug": ("name",)}
    list_display = ['name', 'slug']


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name',]

