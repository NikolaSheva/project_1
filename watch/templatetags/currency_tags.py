from functools import lru_cache

from django import template

from watch.services.exchange import get_usd_rate

register = template.Library()


@lru_cache(maxsize=1)
def get_cached_usd_rate():
    return get_usd_rate()


@register.filter
def usd_to_rub(value):
    """Конвертирует USD в RUB с кэшированием"""
    if isinstance(value, (int, float)):
        return round(float(value) * get_cached_usd_rate())
    return value


@register.filter
def format_currency(value, currency=None):
    """Форматирует цену с валютой"""
    if not isinstance(value, (int, float)):
        return str(value)

    if currency is None:
        currency = "USD"

    currency = currency.upper()
    if currency == "RUB":
        return f"{int(value):,} ₽".replace(",", " ")
    elif currency == "USD":
        if value == int(value):
            return f"${int(value):,}".replace(",", " ")
        return f"${value:,.2f}".replace(",", " ")
    else:
        return f"{value:,} {currency}".replace(",", " ")
