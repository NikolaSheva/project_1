# watch/management/commands/update_characteristics.py
import asyncio
import time
from datetime import timedelta
from typing import Dict, List
from urllib.parse import urljoin

from django.core.management.base import BaseCommand
from django.db import transaction
from loguru import logger
from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from watch.models import Product

BASE_URL = "https://lombard-perspectiva.ru"
console = Console()


class Command(BaseCommand):
    help = "Дозаполняет характеристики товаров"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Сколько товаров обработать")
        parser.add_argument("--batch-size", type=int, default=10, help="Размер пачки")
        parser.add_argument("--debug", action="store_true", default=False)

    def handle(self, *args, **kwargs):
        if kwargs.get('debug'):
            logger.remove()
            logger.add(lambda msg: print(msg), level="DEBUG")
        
        asyncio.run(self.main(
            kwargs.get('limit', 100),
            kwargs.get('batch_size', 10)
        ))

    @sync_to_async
    def get_products_to_update(self, limit: int) -> List[Product]:
        """Получает товары для обновления (синхронная обертка)"""
        return list(Product.objects.filter(
            case_material__isnull=True,
            water_resistance__isnull=True
        )[:limit])

    async def update_product_characteristics(self, products: List[Product]) -> int:
        """Обновляет характеристики для списка товаров"""
        updated = 0
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox']
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            )
            
            try:
                for product in products:
                    page = None
                    try:
                        page = await context.new_page()
                        logger.debug(f"[{updated+1}/{len(products)}] Загрузка: {product.url}")
                        
                        await page.goto(product.url, wait_until="domcontentloaded", timeout=15000)
                        await page.wait_for_timeout(1000)
                        
                        chars = {}
                        
                        # Референс
                        ref_elem = await page.query_selector('div.catalog-item-reference div.text-gray')
                        if ref_elem:
                            ref_text = await ref_elem.text_content()
                            if ref_text:
                                ref_value = ref_text.replace('Референс:', '').strip()
                                if ref_value and not product.ref:
                                    chars['ref'] = ref_value
                        
                        # Состояние
                        badge_elem = await page.query_selector('div.badge-element.badge-blue')
                        if badge_elem:
                            badge_text = await badge_elem.text_content()
                            if badge_text and not product.condition_detail:
                                chars['condition_detail'] = badge_text.strip()
                        
                        # Парсим характеристики из таблицы
                        rows = await page.query_selector_all("div.d-block.d-sm-flex")
                        for row in rows:
                            label = await row.query_selector("div.option-label")
                            value = await row.query_selector("div.option-value")
                            if label and value:
                                label_text = await label.text_content()
                                value_text = await value.text_content()
                                if label_text and value_text:
                                    label_lower = label_text.lower().strip()
                                    value_clean = value_text.strip()
                                    
                                    if "материал корпуса" in label_lower:
                                        if not product.case_material:
                                            chars['case_material'] = value_clean
                                    elif "водонепроницаемость" in label_lower:
                                        if not product.water_resistance:
                                            chars['water_resistance'] = value_clean
                                    elif "диаметр" in label_lower:
                                        if not product.case_diameter:
                                            chars['case_diameter'] = value_clean
                                    elif "материал ремешка" in label_lower:
                                        if not product.strap_material:
                                            chars['strap_material'] = value_clean
                                    elif "механизм" in label_lower:
                                        if not product.movement_type:
                                            chars['movement_type'] = value_clean
                                    elif "стекло" in label_lower:
                                        if not product.glass:
                                            chars['glass'] = value_clean
                                    elif "цвет циферблата" in label_lower:
                                        if not product.dial_color:
                                            chars['dial_color'] = value_clean
                                    elif "коллекция" in label_lower:
                                        if not product.collection:
                                            chars['collection'] = value_clean
                                    elif "функции" in label_lower:
                                        if not product.functions:
                                            chars['functions'] = value_clean
                                    elif "калибр" in label_lower:
                                        if not product.caliber:
                                            chars['caliber'] = value_clean
                                    elif "запас хода" in label_lower:
                                        if not product.power_reserve:
                                            chars['power_reserve'] = value_clean
                        
                        # Обновляем в БД, если есть новые данные
                        if chars:
                            # Используем sync_to_async для сохранения
                            await self.save_product_chars(product.id, chars)
                            updated += 1
                            logger.debug(f"✓ Обновлен {product.title} ({len(chars)} полей)")
                        else:
                            logger.debug(f"- Нет новых данных для {product.title}")
                        
                    except Exception as e:
                        logger.error(f"✗ Ошибка {product.url}: {e}")
                    finally:
                        if page:
                            await page.close()
                    
                    await asyncio.sleep(0.5)  # Задержка между запросами
                    
            finally:
                await context.close()
                await browser.close()
        
        return updated

    @sync_to_async
    def save_product_chars(self, product_id: int, chars: Dict):
        """Сохраняет характеристики в БД (синхронная обертка)"""
        try:
            product = Product.objects.get(id=product_id)
            updated_fields = []
            
            if chars.get('ref'):
                product.ref = chars['ref']
                updated_fields.append('ref')
            
            if chars.get('condition_detail'):
                product.condition_detail = chars['condition_detail']
                updated_fields.append('condition_detail')
            
            if chars.get('case_material'):
                product.case_material = chars['case_material']
                updated_fields.append('case_material')
            
            if chars.get('water_resistance'):
                product.water_resistance = chars['water_resistance']
                updated_fields.append('water_resistance')
            
            if chars.get('case_diameter'):
                product.case_diameter = chars['case_diameter']
                updated_fields.append('case_diameter')
            
            if chars.get('strap_material'):
                product.strap_material = chars['strap_material']
                updated_fields.append('strap_material')
            
            if chars.get('movement_type'):
                product.movement_type = chars['movement_type']
                updated_fields.append('movement_type')
            
            if chars.get('glass'):
                product.glass = chars['glass']
                updated_fields.append('glass')
            
            if chars.get('dial_color'):
                product.dial_color = chars['dial_color']
                updated_fields.append('dial_color')
            
            if chars.get('collection'):
                product.collection = chars['collection']
                updated_fields.append('collection')
            
            if chars.get('functions'):
                product.functions = chars['functions']
                updated_fields.append('functions')
            
            if chars.get('caliber'):
                product.caliber = chars['caliber']
                updated_fields.append('caliber')
            
            if chars.get('power_reserve'):
                product.power_reserve = chars['power_reserve']
                updated_fields.append('power_reserve')
            
            if updated_fields:
                product.save(update_fields=updated_fields)
                logger.debug(f"✓ Сохранены поля для {product.title}: {', '.join(updated_fields)}")
            
        except Product.DoesNotExist:
            logger.error(f"Товар {product_id} не найден")

    @sync_to_async
    def count_remaining(self) -> int:
        """Считает оставшиеся товары для обновления"""
        return Product.objects.filter(
            case_material__isnull=True,
            water_resistance__isnull=True
        ).count()

    async def main(self, limit: int, batch_size: int):
        """Основная функция"""
        start = time.time()
        
        console.print("[bold cyan]🚀 Дозаполнение характеристик[/]")
        
        # Получаем товары для обновления через sync_to_async
        products = await self.get_products_to_update(limit)
        
        if not products:
            console.print("[green]✅ Все товары уже имеют характеристики[/]")
            return
        
        remaining = await self.count_remaining()
        console.print(f"[cyan]📦 Найдено {len(products)} товаров для обработки (осталось всего: {remaining})[/]")
        
        # Разбиваем на пачки
        batches = [products[i:i+batch_size] for i in range(0, len(products), batch_size)]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Обновление характеристик...", total=len(products))
            
            total_updated = 0
            for batch_num, batch in enumerate(batches, 1):
                console.print(f"[dim]Пакет {batch_num}/{len(batches)}...[/]")
                updated = await self.update_product_characteristics(batch)
                total_updated += updated
                progress.update(task, advance=len(batch))
        
        elapsed = time.time() - start
        
        console.print("\n" + "="*50)
        console.print("[bold green]📊 ИТОГИ[/]")
        console.print("="*50)
        console.print(f"📦 Обработано: {len(products)}")
        console.print(f"✅ Обновлено: {total_updated}")
        console.print(f"⏱️  Время: {timedelta(seconds=int(elapsed))}")
        console.print("="*50)