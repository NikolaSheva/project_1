import asyncio
import time
from datetime import timedelta
from typing import List
from urllib.parse import urljoin

from django.core.management.base import BaseCommand
from loguru import logger
from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)

from watch.models import Product, ProductImage

BASE_URL = "https://lombard-perspectiva.ru"
console = Console()


class Command(BaseCommand):
    help = "Сбор дополнительных фото для существующих товаров"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Ограничить количество товаров")
        parser.add_argument("--workers", type=int, default=5, help="Количество параллельных воркеров")
        parser.add_argument("--debug", action="store_true", default=False, help="Режим отладки")
        parser.add_argument("--collect-images", action="store_true", default=True, help="Собирать дополнительные фото")

    def handle(self, *args, **kwargs):
        if kwargs.get('debug'):
            logger.remove()
            logger.add(lambda msg: print(msg), level="DEBUG")
        
        collect_images = kwargs.get('collect-images', True)
        
        asyncio.run(self.main(
            kwargs.get('limit', 100),
            kwargs.get('workers', 5),
            collect_images
        ))

    async def extract_product_images(self, product_url: str) -> List[str]:
        """Сбор всех фото товара со страницы продукта"""
        images = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--start-maximized',
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                await page.goto(product_url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1000)  # Небольшая пауза для загрузки
                
                # Пробуем найти галерею
                gallery_selectors = [
                    "div.catalog-item--photos__grid",
                    "div.catalog-item--photos__wrapper",
                    ".catalog-item--photos",
                    "[class*='catalog-item-photos']"
                ]
                
                gallery_found = False
                for selector in gallery_selectors:
                    gallery = page.locator(selector)
                    if await gallery.count() > 0:
                        gallery_found = True
                        logger.debug(f"✅ Галерея найдена по селектору: {selector}")
                        
                        # Ищем все image_wrapper внутри галереи
                        image_wrappers = await gallery.locator("div.image_wrapper").all()
                        if image_wrappers:
                            logger.debug(f"📸 Найдено image_wrapper: {len(image_wrappers)}")
                            
                            for idx, wrapper in enumerate(image_wrappers):
                                # Ищем изображение внутри wrapper
                                img = wrapper.locator("img").first
                                if await img.count() > 0:
                                    src = await img.get_attribute("src")
                                    if src:
                                        full_url = self._normalize_url(src)
                                        if full_url and full_url not in images:
                                            images.append(full_url)
                                            logger.debug(f"  ✅ Добавлено фото {idx+1}: {full_url[-40:]}")
                        
                        # Если не нашли image_wrapper, ищем все img внутри галереи
                        if not image_wrappers:
                            gallery_images = await gallery.locator("img").all()
                            logger.debug(f"📸 Найдено img в галерее: {len(gallery_images)}")
                            
                            for img in gallery_images:
                                src = await img.get_attribute("src")
                                if src:
                                    full_url = self._normalize_url(src)
                                    if full_url and full_url not in images:
                                        images.append(full_url)
                                        logger.debug(f"  ✅ Добавлено фото: {full_url[-40:]}")
                        break
                
                if not gallery_found:
                    logger.debug("❌ Галерея не найдена")
                    
                    # Запасной вариант - ищем все изображения со страницы
                    all_images = await page.locator("img[src*='/storage/']").all()
                    logger.debug(f"📸 Найдено изображений через запасной селектор: {len(all_images)}")
                    
                    for img in all_images:
                        src = await img.get_attribute("src")
                        if src:
                            full_url = self._normalize_url(src)
                            if full_url and full_url not in images:
                                images.append(full_url)
                                logger.debug(f"  ✅ Добавлено фото (запасной): {full_url[-40:]}")
                
                # Находим основное фото
                main_img = page.locator("img.catalog-item-img--object").first
                main_src = None
                if await main_img.count() > 0:
                    src = await main_img.get_attribute("src")
                    if src:
                        main_src = self._normalize_url(src)
                        logger.debug(f"📌 Основное фото: {main_src[-40:]}")
                
                # Исключаем основное фото
                if main_src and main_src in images:
                    images.remove(main_src)
                    logger.debug("✅ Основное фото исключено")
                
                # Удаляем дубликаты и берем первые 10
                images = list(dict.fromkeys(images))[:10]
                
                if images:
                    logger.debug(f"✅ Найдено {len(images)} уникальных доп. фото")
                    for i, img in enumerate(images, 1):
                        logger.debug(f"   {i}. {img[-40:]}")
                else:
                    logger.debug("❌ Нет доп. фото")
                
            except Exception as e:
                logger.error(f"Ошибка сбора фото: {e}")
            finally:
                await browser.close()
        
        return images

    def _normalize_url(self, src: str) -> str:
        """Нормализует URL изображения"""
        if not src:
            return None
        
        if src.startswith('//'):
            return f"https:{src}"
        elif src.startswith('/'):
            return urljoin(BASE_URL, src)
        elif src.startswith('http'):
            return src
        else:
            return urljoin(BASE_URL, src)

    async def process_product(self, product):
        """Обработка одного товара"""
        try:
            images = await self.extract_product_images(product.url)
            
            if images:
                # Удаляем старые фото
                await sync_to_async(ProductImage.objects.filter(product=product).delete)()
                
                # Создаем новые
                images_to_create = []
                for idx, img_url in enumerate(images[:10]):
                    if img_url != product.image_url:  # Не дублируем основное фото
                        images_to_create.append(
                            ProductImage(
                                product=product,
                                image_url=img_url,
                                order=idx
                            )
                        )
                
                if images_to_create:
                    await sync_to_async(ProductImage.objects.bulk_create)(images_to_create)
                    logger.debug(f"✅ Сохранено {len(images_to_create)} фото для {product.title}")
                    return len(images_to_create)
            else:
                logger.debug(f"❌ Нет доп. фото для {product.title}")
        
        except Exception as e:
            logger.error(f"Ошибка обработки {product.title}: {e}")
        
        return 0

    async def worker(self, queue, results, progress, task):
        """Воркер для обработки товаров из очереди"""
        while True:
            try:
                product = await queue.get()
                if product is None:
                    queue.task_done()
                    break
                
                # Убрал semaphore, так как он не нужен
                count = await self.process_product(product)
                
                if count > 0:
                    results['total_images'] += count
                    results['products_with_images'] += 1
                
                progress.update(task, advance=1)
                queue.task_done()
                
            except Exception as e:
                logger.error(f"Ошибка в воркере: {e}")
                queue.task_done()

    async def main(self, limit: int, workers: int, collect_images: bool):
        """Основная функция"""
        start = time.time()
        
        console.print("[bold cyan]🚀 Запуск сбора дополнительных фото[/]")
        console.print(f"[dim]Параметры: limit={limit}, workers={workers}, collect_images={collect_images}[/]")
        
        if not collect_images:
            console.print("[yellow]⚠️ Сбор фото отключен (collect_images=False)[/]")
            return
        
        # ВАЖНО: импортируем Count здесь
        from django.db.models import Count
        
        # Получаем товары - ТОЛЬКО ТЕ, У КОТОРЫХ НЕТ ДОПОЛНИТЕЛЬНЫХ ФОТО
        queryset = Product.objects.filter(
            image_url__isnull=False
        ).exclude(
            image_url=''
        ).annotate(
            img_count=Count('additional_images')
        ).filter(
            img_count=0  # Только товары без дополнительных фото
        ).order_by('?')
        
        if limit and limit > 0:
            queryset = queryset[:limit]
        
        products = await sync_to_async(list)(queryset)
        
        console.print(f"[cyan]📦 Найдено {len(products)} товаров БЕЗ доп. фото для обработки[/]")
        
        if not products:
            console.print("[green]✅ Все товары уже имеют дополнительные фото![/]")
            return
        
        # Прогресс-бар
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Сбор фото...", total=len(products))
            
            # Создаем очередь и результаты
            queue = asyncio.Queue()
            results = {'total_images': 0, 'products_with_images': 0}
            
            # Заполняем очередь товарами
            for product in products:
                await queue.put(product)
            
            # Добавляем стоп-сигналы для воркеров
            for _ in range(workers):
                await queue.put(None)
            
            # Запускаем воркеров
            worker_tasks = []
            for _ in range(workers):
                worker_task = asyncio.create_task(self.worker(queue, results, progress, task))
                worker_tasks.append(worker_task)
            
            # Ждем завершения всех воркеров
            await asyncio.gather(*worker_tasks)
        
        elapsed = time.time() - start
        minutes = elapsed / 60
        speed = len(products) / minutes if minutes > 0 else 0
        
        console.print("\n" + "="*50)
        console.print("[bold green]📊 ИТОГИ СБОРА ФОТО[/]")
        console.print("="*50)
        console.print(f"📦 Обработано товаров: [bold]{len(products)}[/]")
        console.print(f"🖼️  Найдено фото: [bold]{results['total_images']}[/]")
        console.print(f"✅ Товаров с фото: [bold]{results['products_with_images']}[/]")
        console.print(f"⏱️  Время: [bold]{timedelta(seconds=int(elapsed))}[/]")
        console.print(f"⚡ Скорость: [bold]{speed:.1f} товаров/мин[/]")