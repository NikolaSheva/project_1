import asyncio
import json
import os
import re
import time
import random 
from datetime import timedelta
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urljoin

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.db import transaction
from loguru import logger
from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright, Page, Browser
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from watch.models import Brand, Product, City

from fake_useragent import UserAgent

ua = UserAgent()

BASE_URL = "https://lombard-perspectiva.ru"
START_URL = f"{BASE_URL}/clocks_today/"

# Кэш для брендов
brand_cache = {}

console = Console()


class Command(BaseCommand):
    help = "Быстрый параллельный импорт часов с lombard-perspectiva.ru"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Ограничить количество товаров")
        parser.add_argument("--headless", action="store_true", default=True, help="Headless режим")
        parser.add_argument("--max-pages", type=int, default=0, help="Максимум страниц")
        parser.add_argument("--batch-size", type=int, default=500, help="Размер пачки для сохранения")
        parser.add_argument("--browsers", type=int, default=2, help="Количество параллельных браузеров")
        parser.add_argument("--debug", action="store_true", default=False, help="Режим отладки")
        parser.add_argument("--skip-db", action="store_true", default=False, help="Пропустить сохранение в БД")
        parser.add_argument("--output-json", action="store_true", default=True, help="Сохранить результаты в JSON")
        parser.add_argument("--delay", type=float, default=3.0, help="Задержка между запросами в секундах")

    def handle(self, *args, **kwargs):
        if kwargs.get('debug'):
            logger.remove()
            logger.add(lambda msg: print(msg), level="DEBUG")
        
        asyncio.run(self.main(
            limit=kwargs.get('limit', 0),
            headless=kwargs.get('headless', True),
            max_pages=kwargs.get('max_pages', 0),
            batch_size=kwargs.get('batch_size', 500),
            browsers=kwargs.get('browsers', 2),
            skip_db=kwargs.get('skip_db', False),
            output_json=kwargs.get('output_json', True),
            delay=kwargs.get('delay', 3.0)
        ))

    async def clean_price(self, price_text: str) -> tuple:
        """Очистка цены"""
        if not price_text:
            return None, None
            
        price_text = price_text.strip()
        logger.debug(f"💰 Обработка цены: '{price_text}'")
        
        # Проверяем на "по запросу"
        if "по запросу" in price_text.lower():
            logger.debug("💰 Цена 'По запросу'")
            return None, "По запросу"
        
        # Ищем числа в строке
        digits = re.findall(r'\d+', price_text.replace(' ', ''))
        if digits:
            # Берем первое число (обычно это цена)
            price_str = digits[0]
            try:
                price_int = int(price_str)
                logger.debug(f"💰 Найдена цена: {price_int}")
                return price_int, None
            except (ValueError, TypeError):
                logger.debug(f"💰 Ошибка преобразования числа: {price_str}")
                return None, price_text
        
        # Если не нашли чисел, возвращаем как текст
        logger.debug(f"💰 Цена как текст: '{price_text}'")
        return None, price_text

    async def extract_from_card(self, card) -> Optional[Dict]:
        """Извлечение данных из карточки товара на странице каталога"""
        try:
            link = await card.get_attribute("href")
            if not link:
                return None
            url = urljoin(BASE_URL, link)
            
            # Бренд
            title = ""
            title_elem = card.locator("p.item-name.text-md.text-spectral.ma-0").first
            if await title_elem.count() > 0:
                title = await title_elem.text_content()
                title = title.strip() if title else ""
            
            # Модель
            # Модель - новый селектор из скриншота
            model = ""
            # Пробуем найти элемент с title, который содержит модель
            model_elem = card.locator("p[title].text.text-xl-small.text-light.ma-0").first
            if await model_elem.count() > 0:
                model = await model_elem.text_content()
                model = model.strip() if model else ""
                if model:
                    logger.debug(f"✅ Модель найдена: {model}")
            else:
                # Запасной вариант - ищем по классам
                model_elems = card.locator(".catalog-item--subtitle p, p[title]")
                count = await model_elems.count()
                if count > 0:
                    model_parts = []
                    for i in range(count):
                        text = await model_elems.nth(i).text_content()
                        if text and text.strip():
                            model_parts.append(text.strip())
                    model = " ".join(model_parts)
                    if model:
                        logger.debug(f"✅ Модель найдена (запасной вариант): {model}")

            if not model:
                logger.debug("❌ Модель не найдена")
            
            # Состояние
            # Состояние - ИСПРАВЛЕННАЯ ВЕРСИЯ
            condition_detail = ""

            # Пробуем разные варианты селекторов для состояния
            condition_selectors = [
                "div.status-used__ico.has span.status-used__tooltip",
                "span.status-used__tooltip",
                "div.status-used__tooltip",
                ".status-used__tooltip",
                "[class*='status-used'] [class*='tooltip']",
                ".catalog-item--status .status-used__tooltip",
                "div[class*='status'] span[class*='tooltip']"
            ]

            for selector in condition_selectors:
                try:
                    element = card.locator(selector).first
                    if await element.count() > 0:
                        condition_detail = await element.text_content()
                        if condition_detail:
                            condition_detail = condition_detail.strip().strip('"')
                            logger.debug(f"✅ Состояние найдено по селектору '{selector}': '{condition_detail}'")
                            break
                except (TimeoutError, ConnectionError) as e:
                    logger.warning(f"Временная ошибка: {e}")
                    continue

            if condition_detail:
                logger.debug(f"✅ ИТОГОВОЕ СОСТОЯНИЕ: '{condition_detail}'")
            else:
                logger.debug("❌ Состояние НЕ найдено")
                        
            # Референс
            ref = ""
            ref_span = card.locator("span.catalog-item-ref--text").first
            if await ref_span.count() > 0:
                ref_parent = await ref_span.evaluate("node => node.parentNode.textContent")
                if ref_parent:
                    ref_match = re.search(r'"([^"]+)"', ref_parent)
                    if ref_match:
                        ref = ref_match.group(1)
                    else:
                        ref = ref_parent.replace("Референс:", "").strip().strip('"')
            
            # Цена
            price = None
            price_text = None
            price_elem = card.locator("p.item-price--text").first
            if await price_elem.count() > 0:
                price_str = await price_elem.text_content()
                logger.debug(f"💰 Сырая цена из карточки: '{price_str}'")
                if price_str:
                    price, price_text = await self.clean_price(price_str)
                    logger.debug(f"💰 Результат: price={price}, price_text='{price_text}'")
            
            # Изображение
            img = None
            img_elem = card.locator("div.catalog-item--img img").first
            if await img_elem.count() == 0:
                img_elem = card.locator("img[alt]").first
            
            if await img_elem.count() > 0:
                img_src = await img_elem.get_attribute("src")
                if img_src:
                    img = urljoin(BASE_URL, img_src)
            
            return {
                "url": url,
                "image": img,
                "brand_name": title,
                "model": model,
                "ref": ref,
                "price": price,
                "price_text": price_text,
                "condition_detail": condition_detail,
            }
            
        except Exception as e:
            logger.error(f"Ошибка извлечения из карточки: {e}")
            return None

    async def parse_product_page(self, url: str, context) -> Dict[str, Any]:
        """ИСПРАВЛЕННАЯ ВЕРСИЯ: парсинг страницы товара с характеристиками"""
        page = None
        try:
            logger.debug(f"🔍 Начинаем парсинг {url[-30:]}")
            
            page = await context.new_page()
            page.set_default_timeout(15000)
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=10000)
                logger.debug(f"✅ Страница загружена: {url[-30:]}")
            except Exception as e:
                logger.debug(f"❌ Ошибка загрузки {url[-30:]}: {type(e).__name__}")
                return {}
            
            await page.wait_for_timeout(500)
            
            data = {
                'city_name': '',
                'case_material': '',
                'water_resistance': '',
                'case_diameter': '',
                'strap_material': '',
                'movement_type': '',
                'glass': '',
                'dial_color': '',
            }
            
            # Парсим город
            try:
                page_text = await page.text_content('body')
                
                match = re.search(r'Наличие в городах:\s*([А-Яа-я\s,]+?)(?:\n|$|<|\.)', page_text)
                if match:
                    city_name = match.group(1).strip()
                    city_name = re.sub(r'\s+', ' ', city_name).strip()
                    if ',' in city_name:
                        city_name = city_name.split(',')[0].strip()
                    data['city_name'] = city_name
                    logger.debug(f"🏙️ Найден город: {data['city_name']}")
            except Exception as e:
                logger.debug(f"Ошибка парсинга города: {e}")
            
            # Парсим характеристики - ВАЖНО!
            try:
                # Пробуем найти контейнер с характеристиками
                container = await page.query_selector("div.catalog-item-options-panel-content.d-block.d-md-flex, div.catalog-item--options-panel-content.d-block.d-md-flex, div.v-expansion-panel-content")
                
                if container:
                    # Ищем все строки характеристик
                    rows = await container.query_selector_all("div.d-block.d-sm-flex")
                    
                    if rows:
                        logger.debug(f"🔍 Найдено {len(rows)} характеристик")
                        
                        for row in rows:
                            # Ищем label и value
                            label_elem = await row.query_selector("div.option-label")
                            value_elem = await row.query_selector("div.option-value")
                            
                            if label_elem and value_elem:
                                label_text = await label_elem.text_content()
                                value_text = await value_elem.text_content()
                                
                                if label_text and value_text:
                                    label_text = label_text.strip().lower()
                                    value_text = value_text.strip()
                                    
                                    # Маппинг характеристик
                                    if "материал корпуса" in label_text:
                                        data['case_material'] = value_text
                                        logger.debug(f"  ✅ case_material: {value_text}")
                                    elif "водонепроницаемость" in label_text or "водозащита" in label_text:
                                        data['water_resistance'] = value_text
                                        logger.debug(f"  ✅ water_resistance: {value_text}")
                                    elif "диаметр корпуса" in label_text:
                                        data['case_diameter'] = value_text
                                        logger.debug(f"  ✅ case_diameter: {value_text}")
                                    elif "цвет циферблата" in label_text:
                                        data['dial_color'] = value_text
                                        logger.debug(f"  ✅ dial_color: {value_text}")
                                    elif "механизм" in label_text:
                                        data['movement_type'] = value_text
                                        logger.debug(f"  ✅ movement_type: {value_text}")
                                    elif "материал ремешка" in label_text:
                                        data['strap_material'] = value_text
                                        logger.debug(f"  ✅ strap_material: {value_text}")
                                    elif "стекло" in label_text:
                                        data['glass'] = value_text
                                        logger.debug(f"  ✅ glass: {value_text}")
                    else:
                        logger.debug("❌ Строки характеристик не найдены в контейнере")
                else:
                    logger.debug("❌ Контейнер характеристик не найден")
                    
            except Exception as e:
                logger.debug(f"Ошибка парсинга характеристик: {e}")
            
            # Логируем найденные характеристики
            found_chars = {k: v for k, v in data.items() if v and k != 'city_name'}
            if found_chars:
                logger.debug(f"📊 Найдены характеристики: {list(found_chars.keys())}")
            else:
                logger.debug("❌ ХАРАКТЕРИСТИКИ НЕ НАЙДЕНЫ!")
            
            return data
            
        except Exception as e:
            logger.debug(f"❌ Ошибка в parse_product_page: {e}")
            return {}
        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Не удалось закрыть страницу: {e}")


    async def collect_from_range(self, browser_id: int, playwright, start_page: int, end_page: int, 
                            limit: int, processed_urls: Set[str], delay: float) -> List[Dict]:
        """ОПТИМИЗИРОВАННАЯ ВЕРСИЯ: параллельный парсинг с контролем"""
        browser = None
        items = []
        
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
            # Контекст для навигации
            nav_context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=ua.random
            )
            nav_page = await nav_context.new_page()
            nav_page.set_default_timeout(15000)
            
            # Пул контекстов для товаров (3 штуки)
            product_contexts = []
            for i in range(3):
                ctx = await browser.new_context(user_agent=ua.random)
                product_contexts.append(ctx)
                logger.debug(f"Браузер {browser_id}: создан контекст {i+1} для товаров")
            
            for page_num in range(start_page, end_page + 1):
                if limit and len(items) >= limit:
                    break
                    
                url = f"{START_URL}?page={page_num}"
                
                # Уменьшенная задержка перед загрузкой страницы
                await asyncio.sleep(delay * 0.5)
                
                try:
                    logger.debug(f"Браузер {browser_id}: загрузка стр {page_num}")
                    await nav_page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await nav_page.wait_for_timeout(500)  # Уменьшено
                    
                    cards = await nav_page.locator("a[href^='/clock/']").all()
                    
                    if not cards:
                        logger.warning(f"Браузер {browser_id}: стр {page_num} пуста")
                        continue
                    
                    logger.info(f"Браузер {browser_id}: стр {page_num}, {len(cards)} карточек")
                    
                    # Собираем данные из карточек
                    page_items = []
                    for card in cards:
                        if limit and len(items) + len(page_items) >= limit:
                            break
                        
                        item = await self.extract_from_card(card)
                        if item and item["url"] not in processed_urls:
                            page_items.append(item)
                            processed_urls.add(item["url"])
                    
                    # ОПТИМИЗАЦИЯ: Параллельный парсинг товаров
                    if page_items:
                        # Создаем семафор для контроля параллелизма (макс 3 одновременно)
                        semaphore = asyncio.Semaphore(3)
                        
                        async def parse_item_with_semaphore(item, context_idx):
                            async with semaphore:
                                try:
                                    # Используем контекст из пула по кругу
                                    ctx = product_contexts[context_idx % len(product_contexts)]
                                    
                                    # Парсим страницу товара
                                    product_data = await self.parse_product_page(item["url"], ctx)
                                    
                                    if product_data:
                                        item.update(product_data)
                                    
                                    # Минимальная пауза между запросами
                                    import secrets
                                    delay = secrets.randbelow(41) / 10 + 0.3  # от 0.3 до 4.0
                                    await asyncio.sleep(delay)
                                    return item
                                except Exception as e:
                                    logger.error(f"Ошибка парсинга товара: {e}")
                                    return item  # Возвращаем хотя бы то, что есть
                        
                        # Запускаем задачи параллельно
                        tasks = []
                        for i, item in enumerate(page_items):
                            task = asyncio.create_task(parse_item_with_semaphore(item, i))
                            tasks.append(task)
                        
                        # Ждем завершения всех задач
                        parsed_items = await asyncio.gather(*tasks)
                        items.extend(parsed_items)
                        
                        logger.debug(f"Браузер {browser_id}: стр {page_num}, +{len(parsed_items)} товаров (параллельно)")
                        
                except Exception as e:
                    logger.error(f"Браузер {browser_id}: ошибка на стр {page_num}: {e}")
                
                # Уменьшенная пауза между страницами
                await asyncio.sleep(delay * 0.7)
            
            # Закрываем все контексты
            for ctx in product_contexts:
                await ctx.close()
            await nav_context.close()
            return items
            
        finally:
            if browser:
                await browser.close()
                
                
                

    async def collect_all_items_parallel(self, playwright, limit: int = 0, max_pages: int = 0, 
                                     concurrent_browsers: int = 2, delay: float = 2.0) -> List[Dict]:
        """Сбор всех товаров с использованием нескольких браузеров"""
        
        if not max_pages:
            max_pages = await self.get_total_pages(playwright) or 17
        
        logger.info(f"Всего страниц для парсинга: {max_pages}")
        
        pages_per_browser = (max_pages + concurrent_browsers - 1) // concurrent_browsers
        total_expected = limit if limit else 3000
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Сбор товаров...", total=total_expected)
            
            processed_urls = set()
            
            tasks = []
            for i in range(concurrent_browsers):
                start = i * pages_per_browser + 1
                end = min((i + 1) * pages_per_browser, max_pages)
                
                if start <= end:
                    tasks.append(self.collect_from_range(
                        i + 1, playwright, start, end, limit, processed_urls, delay
                    ))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_items = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Ошибка в задаче: {result}")
                elif result:
                    all_items.extend(result)
                    if limit and len(all_items) >= limit:
                        all_items = all_items[:limit]
                        break
                
                progress.update(task, completed=len(all_items))
        
        return all_items

    async def is_site_available(self) -> bool:
        """Проверяет доступность сайта"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=ua.random)
                page = await context.new_page()
                response = await page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
                title = await page.title()
                await browser.close()
                
                if response and response.status == 200:
                    logger.info(f"✅ Сайт доступен: {response.status}, заголовок: {title}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Сайт недоступен: {e}")
            return False

    async def get_total_pages(self, playwright) -> int:
        """Определение количества страниц"""
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=ua.random)
            page = await context.new_page()
            
            await page.goto(START_URL, wait_until='domcontentloaded', timeout=15000)
            
            pagination = page.locator(".navigation .paginate-link")
            count = await pagination.count()
            
            if count > 0:
                last_page_text = await pagination.nth(count - 1).text_content()
                if last_page_text and last_page_text.isdigit():
                    return int(last_page_text)
            
            await browser.close()
        except Exception as e:
            logger.error(f"Ошибка определения количества страниц: {e}")
        
        return 17

    @sync_to_async
    def save_products_bulk_optimized(self, items: List[Dict]) -> int:
        """Оптимизированное сохранение товаров"""
        if not items:
            return 0
        
        logger.debug("=" * 50)
        logger.debug("🔍 АНАЛИЗ ITEMS ПЕРЕД СОХРАНЕНИЕМ:")
        for idx, item in enumerate(items[:5]):
            condition = item.get("condition_detail", "")
            logger.debug(f"  Товар {idx+1}: {item.get('brand_name')} - СОСТОЯНИЕ: '{condition}'")
            logger.debug("=" * 50)
            city_name = item.get("city_name", "").strip()
            price_text = item.get("price_text", "")
            chars = []
            for field in ['case_material', 'water_resistance', 'case_diameter', 
                        'dial_color', 'movement_type', 'strap_material', 'glass']:
                if item.get(field):
                    chars.append(field)
            
            logger.debug(f"  Товар {idx+1}: {item.get('brand_name')} - ГОРОД: '{city_name}', ЦЕНА(текст): '{price_text}', ХАРАКТЕРИСТИКИ: {len(chars)}")
        logger.debug("=" * 50)
        
        urls = [item["url"] for item in items]
        existing = {p.url: p for p in Product.objects.filter(url__in=urls)}
        
        to_create = []
        to_update = []
        city_cache = {}
        
        for item in items:
            # Бренд
            brand_name = item.get("brand_name", "Неизвестно")
            brand_slug = slugify(brand_name)
            
            if brand_slug in brand_cache:
                brand = brand_cache[brand_slug]
            else:
                brand, _ = Brand.objects.get_or_create(
                    slug=brand_slug, defaults={"name": brand_name}
                )
                brand_cache[brand_slug] = brand
            
            # Город
            city = None
            city_name = item.get("city_name", "").strip()
            if city_name:
                if city_name in city_cache:
                    city = city_cache[city_name]
                else:
                    city, _ = City.objects.get_or_create(name=city_name)
                    city_cache[city_name] = city
            
            # Полное название
            model = item.get("model", "").strip()
            full_title = f"{brand_name} {model}" if model else brand_name
      
            # Подготовка данных
            if item["url"] in existing:
                product = existing[item["url"]]
                product.title = full_title
                product.brand = brand
                product.model = item.get("model", "")
                product.image_url = item.get("image", "")
                product.ref = item.get("ref", "")
                product.condition_detail = item.get("condition_detail", "")
                
                # Сохраняем числовую цену (price_usd)
                if item.get("price") is not None:
                    if isinstance(item["price"], (int, float)):
                        product.price_usd = float(item["price"])
                        logger.debug(f"  💰 Установлена цена USD: {product.price_usd} для {full_title}")
                
                # Сохраняем текстовую цену (price_text) - если есть
                if item.get("price_text"):
                    product.price_text = item["price_text"]
                    logger.debug(f"  💰 Установлен price_text: '{product.price_text}' для {full_title}")
                
                # Характеристики
                if item.get("case_material"):
                    product.case_material = item["case_material"]
                if item.get("water_resistance"):
                    product.water_resistance = item["water_resistance"]
                if item.get("case_diameter"):
                    product.case_diameter = item["case_diameter"]
                if item.get("dial_color"):
                    product.dial_color = item["dial_color"]
                if item.get("movement_type"):
                    product.movement_type = item["movement_type"]
                if item.get("strap_material"):
                    product.strap_material = item["strap_material"]
                if item.get("glass"):
                    product.glass = item["glass"]
                
                to_update.append((product, city))
            else:
                product_data = {
                    "title": full_title,
                    "model": item.get("model", ""),
                    "slug": slugify(full_title)[:50],
                    "brand": brand,
                    "image_url": item.get("image", ""),
                    "url": item["url"],
                    "ref": item.get("ref", ""),
                    "condition_detail": item.get("condition_detail", ""),
                    "case_material": item.get("case_material", ""),
                    "water_resistance": item.get("water_resistance", ""),
                    "case_diameter": item.get("case_diameter", ""),
                    "dial_color": item.get("dial_color", ""),
                    "movement_type": item.get("movement_type", ""),
                    "strap_material": item.get("strap_material", ""),
                    "glass": item.get("glass", ""),
                }
                
                # Добавляем price_text для новых товаров
                price_text = item.get("price_text", "")
                if price_text:
                    product_data["price_text"] = price_text
                    logger.debug(f"  💰 Новый товар с price_text: '{price_text}'")
                
                if item.get("price") is not None and isinstance(item["price"], (int, float)):
                    product_data["price_usd"] = float(item["price"])
                    logger.debug(f"  💰 Новый товар с ценой USD: {item['price']}")
                
                # Добавляем текстовую цену
                if item.get("price_text"):
                    product_data["price_text"] = item["price_text"]
                    logger.debug(f"  💰 Новый товар с price_text: '{item['price_text']}'")
                
                product = Product(**product_data)
                to_create.append((product, city))
        
        saved_count = 0
        with transaction.atomic():
            if to_create:
                products_to_create = [p for p, _ in to_create]
                created_products = Product.objects.bulk_create(products_to_create, batch_size=500)
                saved_count += len(created_products)
                
                for (product, city), created_product in zip(to_create, created_products):
                    if city:
                        created_product.cities.add(city)
                
                logger.info(f"Создано {len(created_products)} новых товаров")
            
            if to_update:
                products_to_update = [p for p, _ in to_update]
                update_fields = ['title', 'model', 'brand', 'image_url', 'ref', 'condition_detail',
                                'case_material', 'water_resistance', 'case_diameter', 
                                'dial_color', 'movement_type', 'strap_material', 'glass']
                
                # Добавляем price_text в поля для обновления, если он есть
                if any(p.price_text for p in products_to_update):
                    update_fields.append('price_text')
                    logger.debug(f"  🔄 Обновление price_text для {sum(1 for p in products_to_update if p.price_text)} товаров")
                
                if any(p.price_usd is not None for p in products_to_update):
                    update_fields.append('price_usd')
                
                Product.objects.bulk_update(products_to_update, update_fields, batch_size=500)
                
                for product, city in to_update:
                    if city:
                        product.cities.clear()
                        product.cities.add(city)
                
                saved_count += len(products_to_update)
                logger.info(f"Обновлено {len(products_to_update)} товаров")
        
        return saved_count

    async def save_products_parallel(self, all_items: List[Dict], batch_size: int):
        """Сохранение товаров пачками"""
        total = len(all_items)
        saved = 0
        
        batches = [all_items[i:i+batch_size] for i in range(0, total, batch_size)]
        
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Сохранение в БД...", total=total)
            
            for batch in batches:
                count = await self.save_products_bulk_optimized(batch)
                saved += len(batch)
                progress.update(task, advance=len(batch))
                logger.info(f"Прогресс сохранения: {saved}/{total}")
        
        return saved

    async def main(self, limit: int, headless: bool, max_pages: int, batch_size: int, 
               browsers: int, skip_db: bool, output_json: bool, delay: float):
        """Основная функция"""
        start = time.time()
        
        console.print("[bold yellow]⚠️ Проверка доступности сайта...[/]")
        if not await self.is_site_available():
            console.print("[red]❌ Сайт недоступен[/]")
            return
        
        console.print("[bold cyan]🚀 Запуск парсера lombard-perspectiva.ru[/]")
        console.print(f"[cyan]Параметры: браузеры={browsers}, задержка={delay}с[/]")
        
        async with async_playwright() as playwright:
            all_items = await self.collect_all_items_parallel(
                playwright, limit, max_pages, browsers, delay
            )
            
            if not all_items:
                console.print("[red]❌ Не найдено товаров[/]")
                return
            
            console.print(f"[green]✅ Собрано {len(all_items)} товаров[/]")
            
            if output_json:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"fetch_watches_{timestamp}.json"
                self.save_results_to_json(all_items, filename)
            
            saved = 0
            if not skip_db:
                console.print("[cyan]💾 Сохранение в базу данных...[/]")
                saved = await self.save_products_parallel(all_items, batch_size)
        
        elapsed = time.time() - start
        rate = len(all_items) / (elapsed / 3600) if elapsed > 0 else 0
        
        console.print("\n" + "="*50)
        console.print("[bold green]📊 ИТОГИ ИМПОРТА[/]")
        console.print("="*50)
        console.print(f"📦 Товаров: [bold]{len(all_items)}[/]")
        console.print(f"⏱️ Время: [bold]{timedelta(seconds=int(elapsed))}[/]")
        console.print(f"⚡ Скорость: [bold]{rate:.0f} товаров/час[/]")
        if not skip_db:
            console.print(f"✅ Сохранено в БД: [bold]{saved}[/]")
        console.print("="*50)

    def save_results_to_json(self, results, filename):
        """Сохраняет результаты в JSON файл"""
        os.makedirs("output", exist_ok=True)
        output_path = os.path.join("output", filename)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            console.print(f"[bold blue] Результаты сохранены в {output_path}[/]")
        except Exception as e:
            console.print(f"[red] Ошибка сохранения файла: {e}[/]")