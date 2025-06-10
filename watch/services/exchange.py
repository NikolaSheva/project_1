import requests
from django.core.cache import cache


def get_usd_rate():
    """Получаем текущий курс USD/RUB с кэшированием (через open.er-api.com)"""
    cache_key = "current_usd_rate"
    rate = cache.get(cache_key)
    if rate is None:
        try:
            response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = data["rates"]["RUB"]
            cache.set(cache_key, rate, 60 * 60 * 6)  # Кэшируем на 6 часов
        except (requests.RequestException, KeyError):
            rate = 75.0  # fallback значение
            cache.set(cache_key, rate, 60 * 60)

    return rate
