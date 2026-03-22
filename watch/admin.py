from django.contrib import admin
from django.utils.html import format_html

from .models import Brand, City, Product, FilterPreset, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    filter_horizontal = ["cities"]
    list_filter = ["brand", "model", "cities"]
    list_display = [ 
        "brand_name",
        "model",
        "cities_list", 
        "ref", 
        "condition_detail", 
        "price_usd"
    ]
    list_per_page = 50
    search_fields = ["model", "brand__name", "ref"]
    
    inlines = [ProductImageInline]
    
    def brand_name(self, obj):
        return obj.brand.name if obj.brand else "-"
    brand_name.short_description = "Бренд"
    brand_name.admin_order_field = 'brand__name'
    
    def cities_list(self, obj):
        return ", ".join([city.name for city in obj.cities.all()]) or "-"
    cities_list.short_description = "Города"
    
    def price_usd(self, obj):
        if obj.price_usd:
            return f"{obj.price_usd:,.0f} $".replace(",", " ")
        return "По запросу"
    price_usd.short_description = "Цена"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_display = ["name", "slug"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'order', 'image_url']
    

@admin.register(FilterPreset)
class FilterPresetAdmin(admin.ModelAdmin):
    filter_horizontal = ["brand", "in_stock"]
    list_display = ["name", "is_active", "created_at"]