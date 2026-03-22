# watch/management/commands/send_to_telegram.py
import asyncio
import random
import socket  # ДОБАВЛЕНО
import time    # ДОБАВЛЕНО
from datetime import timedelta
from typing import List, Tuple, Dict
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from django.conf import settings
from loguru import logger
from rich.console import Console
from asgiref.sync import sync_to_async

from watch.models import Product

console = Console()


class LombardParser:
    """Парсер, использующий данные из модели Product с дозаполнением с сайта"""
    
    def __init__(self, product):
        self.product = product
        self.soup = None
        self.base_url = None
        self.parsed_data = {}
    
    def parse_from_model(self) -> Tuple[str, List[str]]:
        """Формирует сообщение, используя данные из БД"""
        try:
            # Получаем данные напрямую из модели Product
            brand = self.product.title or ""  # В title хранится бренд
            model = self.product.model or ""  # В model хранится модель
            reference = self.product.ref or ""
            condition = self.product.condition_detail or ""
            price = self.product.price_usd
            price_text = self.product.price_text or ""
            
            logger.debug(f"Формирование сообщения для {brand} {model}")
            logger.debug(f"  - Референс: {reference}")
            logger.debug(f"  - Состояние (сырое): '{condition}'")
            logger.debug(f"  - Цена USD: {price}")
            logger.debug(f"  - Цена текст: {price_text}")
            
            # Формируем HTML
            lines = []
            
            # Первая строка: бренд и модель (если есть)
            if brand:
                if model and model.strip():
                    lines.append(f'<a href="{self.product.url}"><b>{brand} {model.upper()}</b></a>')
                else:
                    lines.append(f'<a href="{self.product.url}"><b>{brand}</b></a>')
            
            # Добавляем референс (если есть)
            if reference:
                safe_reference = f"Референс: {str(reference).replace('.', '.\u200B')}"
                lines.append(f'<code>{safe_reference}</code>\n')
            
            # Добавляем состояние (УЛУЧШЕНО)
            if condition and condition.strip() and condition.lower() not in ["нет", "none", "null", ""]:
                lines.append(f'<b>Состояние:</b> {condition.strip()}')
                logger.debug(f"  ✅ Состояние добавлено: {condition.strip()}")
            else:
                logger.debug(f"  ⚠️ Состояние пропущено (пустое или 'нет'): '{condition}'")
            
            # Характеристики (только те, что есть)
            important_chars = [
                ("Материал корпуса", self.product.case_material or ''),
                ("Водонепроницаемость", self.product.water_resistance or ''),
                ("Диаметр", self.product.case_diameter or ''),
                ("Материал ремешка", self.product.strap_material or ''),
                ("Механизм", self.product.movement_type or ''),
                ("Стекло", self.product.glass or ''),
                ("Циферблат", self.product.dial_color or ''),
            ]
            
            chars_added = 0
            for key, value in important_chars:
                if value and value != "Нет данных" and value.strip():
                    lines.append(f'<b>{key}:</b> {value}')
                    chars_added += 1
                    logger.debug(f"  ✅ Характеристика {key}: {value}")
            
            if chars_added > 0:
                logger.debug(f"  ✅ Добавлено характеристик: {chars_added}")
                lines.append("")  # Пустая строка после характеристик
            
            # Добавляем цену
            if price:
                price_str = f"{int(price)} $" if float(price).is_integer() else f"{price} $"
                lines.append(f'<b>Цена:</b> <b>{price_str}</b>\n')
                logger.debug(f"  ✅ Цена добавлена: {price_str}")
            elif price_text and price_text.strip():
                lines.append(f'<b>Цена:</b> <b>{price_text}</b>\n')
                logger.debug(f"  ✅ Цена (текст) добавлена: {price_text}")
            else:
                lines.append(f'<b>Цена:</b> <b>По запросу</b>\n')
                logger.debug(f"  ⚠️ Цена по умолчанию: 'По запросу'")
            
            # Добавляем контакты из настроек
            if lines:  # Добавляем контакты только если есть хоть какой-то контент
                for i, c in enumerate(settings.CONTACTS):
                    lines.append(c["address"])
                    if "tel" in c:
                        lines.append(f'tel:{c["tel"]}  |  <a href="{c["wa_link"]}">WhatsApp</a>')
                    if i < len(settings.CONTACTS) - 1:
                        lines.append("")
            
            html = "\n".join(lines)
            logger.debug(f"ИТОГОВОЕ СООБЩЕНИЕ:\n{html[:500]}...")  # Первые 500 символов
            
            # Собираем фото
            photos = self._collect_photos()
            
            return html.strip(), photos
            
        except Exception as e:
            logger.error(f"Ошибка формирования сообщения для {self.product.url}: {e}")
            return self._get_fallback_data()
        
    def _parse_page(self):
        """Парсит страницу товара для получения недостающих данных"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.product.url, headers=headers, timeout=30)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.text, "lxml")
            
            # Парсим референс
            ref_tag = self.soup.find("div", class_="text-gray")
            if ref_tag:
                ref_text = ref_tag.get_text(strip=True)
                self.parsed_data['reference'] = ref_text.replace("Референс:", "").strip()
            
            # Парсим состояние
            condition_tag = self.soup.find("div", class_="flex-shrink-0")
            if condition_tag:
                self.parsed_data['condition'] = condition_tag.get_text(strip=True).strip('"')
            
            # Парсим характеристики из таблицы
            rows = self.soup.select("div.d-block.d-sm-flex.flex-nowrap.justify-space-between.align-baseline.my-2")
            for row in rows:
                label = row.find("div", class_="option-label")
                value = row.find("div", class_="option-value")
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)
                    
                    if "материал корпуса" in label_text:
                        self.parsed_data['case_material'] = value_text
                    elif "водонепроницаемость" in label_text:
                        self.parsed_data['water_resistance'] = value_text
                    elif "диаметр корпуса" in label_text:
                        self.parsed_data['case_diameter'] = value_text
                    elif "материал ремешка" in label_text:
                        self.parsed_data['strap_material'] = value_text
                    elif "механизм" in label_text:
                        self.parsed_data['movement_type'] = value_text
                    elif "стекло" in label_text:
                        self.parsed_data['glass'] = value_text
                    elif "цвет циферблата" in label_text:
                        self.parsed_data['dial_color'] = value_text
            
            logger.debug(f"Спарсены данные для {self.product.url}: {self.parsed_data}")
            
        except Exception as e:
            logger.error(f"Ошибка парсинга {self.product.url}: {e}")
    
    def _update_product(self):
        """Обновляет продукт в БД спарсенными данными"""
        updated = False
        update_fields = []
        
        if self.parsed_data.get('reference') and not self.product.ref:
            self.product.ref = self.parsed_data['reference']
            update_fields.append('ref')
            updated = True
        
        if self.parsed_data.get('condition') and not self.product.condition_detail:
            self.product.condition_detail = self.parsed_data['condition']
            update_fields.append('condition_detail')
            updated = True
        
        # Обновляем характеристики
        char_fields = [
            ('case_material', 'case_material'),
            ('water_resistance', 'water_resistance'),
            ('case_diameter', 'case_diameter'),
            ('strap_material', 'strap_material'),
            ('movement_type', 'movement_type'),
            ('glass', 'glass'),
            ('dial_color', 'dial_color'),
        ]
        
        for parsed_key, model_field in char_fields:
            if self.parsed_data.get(parsed_key) and not getattr(self.product, model_field):
                setattr(self.product, model_field, self.parsed_data[parsed_key])
                update_fields.append(model_field)
                updated = True
        
        if updated:
            self.product.save(update_fields=update_fields)
            logger.info(f"Обновлен продукт {self.product.id} с полями: {', '.join(update_fields)}")
    
    def _collect_photos(self) -> List[str]:
        """Собирает фото из модели"""
        seen_urls = set()
        photos = []
        
        # Основное фото товара
        if self.product.image_url and "noimage" not in self.product.image_url.lower():
            seen_urls.add(self.product.image_url)
            photos.append(self.product.image_url)
        
        # Дополнительные фото
        for img in self.product.additional_images.all().order_by('order'):
            if img.image_url not in seen_urls and "noimage" not in img.image_url.lower():
                seen_urls.add(img.image_url)
                photos.append(img.image_url)
        
        max_photos = getattr(settings, 'MAX_PHOTOS', 10)
        return photos[:max_photos]
    
    def _get_fallback_data(self) -> Tuple[str, List[str]]:
        """Запасной вариант"""
        title = self.product.title or "Неизвестно"
        
        if title and ' ' in title:
            parts = title.split(' ', 1)
            brand = parts[0]
            model = parts[1] if len(parts) > 1 else ""
        else:
            brand = title
            model = ""
        
        lines = [
            f'<a href="{self.product.url}"><b>{brand}</b>  <b>{model.upper()}</b></a>',
            f'<code>Референс не найден</code>\n',
            f'<b>Состояние:</b> Неизвестно\n',
            f'<b>Цена:</b> <b>{self.product.price_usd if self.product.price_usd else "По запросу"} USD</b>\n',
        ]
        
        for i, c in enumerate(settings.CONTACTS):
            lines.append(c["address"])
            if "tel" in c:
                lines.append(f'tel:{c["tel"]}  |  <a href="{c["wa_link"]}">WhatsApp</a>')
            if i < len(settings.CONTACTS) - 1:
                lines.append("")
        
        html = "\n".join(lines)
        
        photos = self._collect_photos()
        
        return html.strip(), photos


class Command(BaseCommand):
    help = "Отправляет товары с фото в Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1, help="Сколько товаров отправить")
        parser.add_argument("--min-photos", type=int, default=2, help="Минимум фото")
        parser.add_argument("--random", action="store_true", default=True, help="Случайный выбор")
        parser.add_argument("--bot-token", type=str, required=True, help="Токен Telegram бота")
        parser.add_argument("--channel-id", type=str, required=True, help="ID канала (@channel или -100...")
        parser.add_argument("--dry-run", action="store_true", default=False, help="Тестовый режим без отправки")

    def check_internet_connection(self):
        """Проверяет наличие интернета и доступность DNS для Telegram"""
        try:
            # Проверка базового интернета (Google DNS)
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            
            # Проверка DNS для Telegram
            telegram_ip = socket.gethostbyname('api.telegram.org')
            self.stdout.write(self.style.SUCCESS(f"✅ DNS работает: api.telegram.org -> {telegram_ip}"))
            
            # Проверка доступности Telegram API
            test_url = f"https://api.telegram.org"
            response = requests.get(test_url, timeout=10)
            if response.status_code < 500:  # Любой ответ кроме 5xx
                self.stdout.write(self.style.SUCCESS(f"✅ Telegram API доступен"))
                return True
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Telegram API вернул статус {response.status_code}"))
                return False
                
        except socket.gaierror as e:
            self.stdout.write(self.style.ERROR(f"❌ DNS ошибка: не могу найти api.telegram.org - {e}"))
            return False
        except socket.timeout:
            self.stdout.write(self.style.ERROR("❌ Таймаут при проверке соединения"))
            return False
        except ConnectionRefusedError:
            self.stdout.write(self.style.ERROR("❌ Соединение отклонено"))
            return False
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка при проверке Telegram API: {e}"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Неизвестная ошибка: {e}"))
            return False

    def handle(self, *args, **kwargs):
        # ИСПРАВЛЕНО: Добавлена проверка интернета в начале
        self.stdout.write(self.style.NOTICE("🔄 Проверка подключения к интернету..."))
        
        max_wait_time = 300  # 5 минут максимум ожидания
        waited_time = 0
        wait_interval = 15   # Проверка каждые 15 секунд
        
        internet_available = False
        
        while waited_time < max_wait_time:
            if self.check_internet_connection():
                internet_available = True
                break
            else:
                if waited_time == 0:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Нет подключения к интернету. Буду ждать до {max_wait_time}с..."
                    ))
                
                self.stdout.write(self.style.WARNING(
                    f"⏳ Ожидание {wait_interval}с... (прошло {waited_time}/{max_wait_time}с)"
                ))
                time.sleep(wait_interval)
                waited_time += wait_interval
        
        if not internet_available:
            self.stdout.write(self.style.ERROR(
                f"❌ Интернет так и не появился за {max_wait_time}с. Отмена отправки."
            ))
            return
        
        self.stdout.write(self.style.SUCCESS("✅ Интернет доступен, начинаем отправку..."))
        
        # ДАЛЬШЕ ИДЁТ ВАШ ОСНОВНОЙ КОД
        bot_token = kwargs['bot_token']
        channel_id = kwargs['channel_id']
        limit = kwargs['limit']
        min_photos = kwargs['min_photos']
        random_order = kwargs['random']
        dry_run = kwargs.get('dry_run', False)
        
        # Находим товары с фото
        queryset = Product.objects.filter(
            additional_images__isnull=False
        ).annotate(
            photos_count=models.Count('additional_images')
        ).filter(
            photos_count__gte=min_photos - 1
        ).exclude(
            telegram_sent_at__isnull=False
        )
        
        if random_order:
            queryset = queryset.order_by('?')
        else:
            queryset = queryset.order_by('-created_at')
        
        products = queryset[:limit]
        
        if not products:
            console.print("[yellow]⚠️ Нет товаров для отправки[/]")
            return
        
        console.print(f"[cyan]📦 Найдено {len(products)} товаров для отправки[/]")
        
        for product in products:
            try:
                parser = LombardParser(product)
                html_message, photos = parser.parse_from_model()
                
                # Отладка
                console.print(f"[dim]📄 Товар: {product.title or 'Без названия'}[/]")
                console.print(f"[dim]  ├─ Референс: {product.ref or 'Нет'}[/]")
                console.print(f"[dim]  ├─ Цена: {product.price_usd or 'Нет'} USD[/]")
                console.print(f"[dim]  ├─ Состояние: {product.condition_detail or 'Нет'}[/]")
                console.print(f"[dim]  └─ Фото: {len(photos)}[/]")
                
                if dry_run:
                    console.print("[yellow]🧪 DRY RUN - отправка отключена[/]")
                    console.print(html_message)
                else:
                    # Отправляем в Telegram
                    self.send_to_telegram(bot_token, channel_id, html_message, photos)
                    
                    # Отмечаем как отправленное
                    product.telegram_sent_at = timezone.now()
                    product.save()
                    
                    console.print(f"[green]✅ Отправлено: {product.title or 'Без названия'}[/]")
                
            except Exception as e:
                logger.error(f"Ошибка отправки {product.title}: {e}")
                console.print(f"[red]❌ Ошибка: {product.title} - {e}[/]")
    
    def send_to_telegram(self, token, chat_id, message, photos):
        """Безопасная отправка медиагруппы в Telegram с повторными попытками"""
        import time
        import random
        from requests.exceptions import ConnectionError, Timeout, RequestException
        
        url = f"https://api.telegram.org/bot{token}/sendMediaGroup"
        
        # Разбиваем фото на группы по 10 (ограничение Telegram)
        max_photos_per_group = 10
        photo_groups = [photos[i:i + max_photos_per_group] for i in range(0, len(photos), max_photos_per_group)]
        
        all_results = []
        
        for group_idx, photo_group in enumerate(photo_groups):
            # Формируем медиа-группу
            media = []
            for i, photo_url in enumerate(photo_group):
                # Только первое фото в первой группе получает полное описание
                # Остальные фото получают пустое описание или короткое примечание
                if group_idx == 0 and i == 0:
                    caption = message
                elif i == 0 and group_idx > 0:
                    # Для первой фото в последующих группах - короткое примечание
                    caption = f"📸 Продолжение (часть {group_idx + 1})"
                else:
                    caption = ""
                
                media.append({
                    'type': 'photo',
                    'media': photo_url,
                    'caption': caption,
                    'parse_mode': 'HTML'
                })
            
            # Добавляем задержку перед отправкой группы (кроме первой)
            if group_idx > 0:
                delay = random.uniform(2, 4)  # nosec B311
                logger.info(f"Ожидание {delay:.1f}с перед отправкой части {group_idx + 1}...")
                time.sleep(delay)
            
            # Отправляем с повторными попытками
            max_retries = 5
            retry_delay = 3
            
            for attempt in range(max_retries):
                try:
                    # Добавляем случайную задержку перед каждой попыткой
                    if attempt > 0:
                        jitter = random.uniform(1, 3)  # nosec B311 
                        wait_time = retry_delay * (2 ** (attempt - 1)) + jitter
                        logger.info(f"Повторная попытка {attempt + 1} через {wait_time:.1f}с...")
                        time.sleep(wait_time)
                    
                    # Отправляем запрос с таймаутом
                    response = requests.post(
                        url, 
                        json={'chat_id': chat_id, 'media': media},
                        timeout=30  # Таймаут 30 секунд
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Часть {group_idx + 1} успешно отправлена")
                        all_results.append(response.json())
                        break  # Успешно отправили, выходим из цикла повторных попыток
                    else:
                        error_text = response.text
                        logger.error(f"Ошибка Telegram (статус {response.status_code}): {error_text}")
                        
                        # Проверяем специфические ошибки Telegram
                        if response.status_code == 429:  # Too Many Requests
                            retry_after = int(response.json().get('parameters', {}).get('retry_after', 10))
                            logger.warning(f"Flood control, ожидание {retry_after}с...")
                            time.sleep(retry_after)
                        elif response.status_code >= 500:  # Ошибки сервера Telegram
                            logger.warning("Ошибка сервера Telegram, повтор через 10с...")
                            time.sleep(10)
                        else:
                            # Другие ошибки - пробуем еще раз
                            if attempt < max_retries - 1:
                                continue
                            else:
                                raise Exception(f"Telegram error: {response.status_code} - {error_text}")
                                
                except (ConnectionError, Timeout, ConnectionResetError) as e:
                    logger.warning(f"Ошибка соединения (попытка {attempt + 1}/{max_retries}): {e}")
                    
                    if attempt == max_retries - 1:  # Последняя попытка
                        # Пробуем отправить хотя бы одно фото отдельно
                        try:
                            logger.info("Пробуем отправить фото по отдельности...")
                            self._send_photos_individually(token, chat_id, photo_group, group_idx, message)
                            break
                        except Exception as inner_e:
                            logger.error(f"Не удалось отправить даже отдельные фото: {inner_e}")
                            raise
                    else:
                        # Продолжаем попытки
                        continue
                        
                except RequestException as e:
                    logger.error(f"Ошибка запроса: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(retry_delay * (2 ** attempt))
            
            # Дополнительная задержка после успешной отправки группы
            if group_idx < len(photo_groups) - 1:  # Если есть еще группы
                time.sleep(random.uniform(3, 5))  # nosec B311
        
        return all_results

    def _send_photos_individually(self, token, chat_id, photos, group_idx, main_message):
        """Отправляет фото по одному, если группа не отправилась"""
        import time
        import random
        
        send_photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        
        for i, photo_url in enumerate(photos):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Для первого фото первой группы отправляем с описанием
                    caption = main_message if group_idx == 0 and i == 0 else ""
                    
                    data = {
                        'chat_id': chat_id,
                        'photo': photo_url,
                        'caption': caption,
                        'parse_mode': 'HTML'
                    }
                    
                    response = requests.post(send_photo_url, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Фото {i+1}/{len(photos)} отправлено")
                        break
                    else:
                        logger.warning(f"Ошибка отправки фото {i+1}: {response.text}")
                        
                except Exception as e:
                    logger.warning(f"Ошибка при отправке фото {i+1} (попытка {attempt+1}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(2, 4))  # nosec B311 
                    else:
                        logger.error(f"Не удалось отправить фото {i+1}")
            
            # Задержка между отдельными фото
            time.sleep(random.uniform(1, 2))  # nosec B311

    async def parse_product_page(self, url: str) -> Dict[str, str]:
        """Парсит отдельную страницу товара"""
        try:
            async with BrowserManager(headless=True) as manager:
                async with manager.page_context() as page:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    data = {}
                    
                    # Парсим состояние
                    condition = await self.get_text_content(page, "div.flex-shrink-0")
                    if condition:
                        data['condition'] = condition.strip().strip('"')
                    
                    # Парсим референс (если его нет в карточке)
                    if not data.get('condition'):
                        ref = await self.get_text_content(page, "div.text-gray")
                        if ref:
                            data['reference'] = ref.replace("Референс:", "").strip()
                    
                    # Парсим характеристики
                    characteristics = {}
                    rows = await page.query_selector_all("div.d-block.d-sm-flex.flex-nowrap.justify-space-between.align-baseline.my-2")
                    for row in rows:
                        label = await row.query_selector("div.option-label")
                        value = await row.query_selector("div.option-value")
                        if label and value:
                            label_text = await label.text_content()
                            value_text = await value.text_content()
                            if label_text and value_text:
                                characteristics[label_text.strip()] = value_text.strip()
                    
                    data['characteristics'] = characteristics
                    
                    return data
                    
        except Exception as e:
            console.print(f"[red] Ошибка парсинга страницы {url}: {e}[/]")
            return {}