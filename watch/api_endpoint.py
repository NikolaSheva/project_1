# api_endpoint.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.utils import timezone
from django.db.models import Count

from watch.models import Product  # только то, что нужно для этого файла
from watch.management.commands.send_to_telegram import LombardParser


@csrf_exempt
def get_unsent_products(request):
    """Возвращает товары для отправки"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    limit = data.get('limit', 1)
    min_photos = data.get('min_photos', 2)
    
    # Получаем товары с фото
    products = Product.objects.filter(
        additional_images__isnull=False
    ).annotate(
        photos_count=Count('additional_images')
    ).filter(
        photos_count__gte=min_photos - 1,
        telegram_sent_at__isnull=True
    ).order_by('?')[:limit]
    
    result = []
    for product in products:
        try:
            parser = LombardParser(product)
            message, photos = parser.parse_from_model()
            result.append({
                'id': product.id,
                'message': message,
                'photos': photos[:10],  # ограничиваем 10 фото
                'title': str(product.title) if product.title else "Без названия",
                'ref': product.ref or "",
            })
        except Exception as e:
            print(f"Ошибка обработки товара {product.id}: {e}")
            continue
    
    return JsonResponse({
        'success': True,
        'products': result,
        'count': len(result)
    })


@csrf_exempt
def mark_as_sent(request):
    """Отмечает товары как отправленные"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    product_ids = data.get('product_ids', [])
    
    if product_ids:
        updated = Product.objects.filter(id__in=product_ids).update(
            telegram_sent_at=timezone.now()
        )
        return JsonResponse({
            'status': 'ok',
            'updated': updated,
            'product_ids': product_ids
        })
    
    return JsonResponse({'status': 'ok', 'updated': 0})


@csrf_exempt
def health_check(request):
    """Проверка работоспособности API"""
    return JsonResponse({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'database': 'sqlite3'
    })