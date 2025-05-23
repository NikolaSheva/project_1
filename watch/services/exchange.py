import requests
from django.core.cache import cache
from django.conf import settings


def get_usd_rate():
    """Получаем текущий курс USD/RUB с кэшированием"""
    cache_key = 'current_usd_rate'
    rate = cache.get(cache_key)

    if rate is None:
        try:
            response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js', timeout=3)
            response.raise_for_status()
            data = response.json()
            rate = data['Valute']['USD']['Value']
            cache.set(cache_key, rate, 60 * 60 * 12)  # Кэшируем на 12 часов
        except (requests.RequestException, KeyError):
            rate = 75.0  # Значение по умолчанию при ошибке
            cache.set(cache_key, rate, 60 * 60)  # Кэшируем фолбек на 1 час

    return rate