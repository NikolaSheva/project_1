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

    # def save_product(self, product_data):
    #     def get_unique_slug(model, base_value):
    #         slug = slugify(base_value)
    #         unique_slug = slug
    #         index = 1
    #         while model.objects.filter(slug=unique_slug).exists():
    #             unique_slug = f"{slug}-{index}"
    #             index += 1
    #         return unique_slug
    #
    #     product = Product.objects.create(
    #         title=product_data['title'],
    #         brand=product_data['brand'],
    #         # other fields initialization
    #     )
    #
    #     if product_data['city']:
    #         city_names = [c.strip() for c in product_data['city'].splitlines() if c.strip()]
    #         city_objs = []
    #         for name in city_names:
    #             base_slug = slugify(name)
    #             city = City.objects.filter(slug=base_slug).first()
    #             if not city:
    #                 unique_slug = get_unique_slug(City, name)
    #                 city = City.objects.create(name=name, slug=unique_slug)
    #             city_objs.append(city)
    #         product.cities.set(city_objs)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    prepopulated_fields = {"slug": ("name",)}
    list_display = ['name', 'slug']

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name',]

