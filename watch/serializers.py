from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'url', 'price',
            'image_url', 'brand', 'special_offer', 'in_stock'
        ]