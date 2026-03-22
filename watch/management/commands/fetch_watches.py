import asyncio
import random
import re
import time
from datetime import timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from fake_useragent import UserAgent
from loguru import logger
from lxml import html

from watch.models import Brand, City, Product

# === Константы ===
BASE_URL = "https://lombard-perspectiva.ru"
MAX_PRODUCTS_PER_PAGE = 180
CONCURRENCY_LIMIT = 10
RETRIES = 3
# HEADERS = partial(lambda ua: {'User-Agent': ua.random}, UserAgent())
ua = UserAgent()

WATCHES = [
    "Неизвестно",
    "AET REMOULD",
    "Alain Silberstein",
    "A. Lange & Sohne",
    "Antoine Preziuso",
    "Arnold & Son",
    "ARTYA",
    "Audemars Piguet",
    "BADOLLET",
    "Bell & Ross",
    "Blancpain",
    "BLU",
    "Bovet",
    "Breguet",
    "Breitling",
    "Bvlgari",
    "Carl F.Bucherer",
    "Cartier",
    "Cecil Purnell",
    "CHAUMET",
    "Chopard",
    "Christophe Claret",
    "Chronoswiss",
    "Clerc",
    "Corum",
    "Cvstos",
    "Czapek",
    "Daniel Roth",
    "De Bethune",
    "De grisogono",
    "Delaneau",
    "De Witt",
    "EDOUARD KOEHN",
    "FP Journe",
    "Franck Muller",
    "Franc Vila",
    "Frédéric Jouvenot",
    "Frederique Constant",
    "Gerald Charles",
    "Gerald Genta",
    "Girard Perregaux",
    "Glashutte Original",
    "GRAFF",
    "Graham",
    "Greubel Forsey",
    "Harry Winston",
    "HD 3",
    "H. Moser & Cie",
    "Hublot",
    "Ice Link",
    "IWC",
    "Jacob & Co",
    "Jaeger LeCoultre",
    "Jaquet Droz",
    "Jean Dunand",
    "JeanRichard",
    "Jorg Hysek",
    "Laurent Ferrier",
    "L'epee",
    "Longines",
    "Louis Moinet",
    "Maikou Bode",
    "Maurice Lacroix",
    "MB&F",
    "Nivrel",
    "Omega",
    "Panerai",
    "Parmigiani Fleurier",
    "Patek Philippe",
    "Perrelet",
    "Piaget",
    "Pierre Kunz",
    "Quinting",
    "RAFFAEL PAPIAN",
    "Ressence",
    "Richard Mille",
    "Roger Dubuis",
    "Rolex",
    "Romain Jerome",
    "Tag Heuer",
    "THOMAS PRESCHER",
    "Tiffany & Co",
    "Tudor",
    "Ulysse Nardin",
    "Urwerk",
    "Vacheron Constantin",
    "Van Cleef & Arpels",
    "Wyler",
    "Zenith",
]
CITIES = [
    "Москва",
    "ТЦ РигаМолл",
    "Санкт-Петербург",
    "Ростов-на-Дону",
    "Краснодар",
    "Екатеринбург",
    "Ташкент",
]


def make_headers() -> Dict[str, str]:
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://lombard-perspectiva.ru/",
        "DNT": "1",
    }


class Command(BaseCommand):
    help = "Асинхронный импорт часов с lombard-perspectiva.ru"

    def handle(self, *args, **kwargs):
        asyncio.run(self.main())

    async def fetch(
        self, session: aiohttp.ClientSession, url: str, retries: int = RETRIES
    ) -> Optional[str]:
        timeout = aiohttp.ClientTimeout(total=20)
        headers = make_headers()
        for attempt in range(retries):
            try:
                async with session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        text = await response.text()
                        logger.debug(f"Ответ сервера ({response.status}): {text[:300]}")
                    logger.warning(
                        f"Попытка {attempt + 1}: Ошибка {response.status} при загрузке {url}"
                    )
            except (
                aiohttp.ClientResponseError,
                asyncio.TimeoutError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientConnectorError,
            ) as e:
                logger.warning(
                    f"Попытка {attempt + 1}: {type(e).__name__} для {url}: {e}"
                )
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}: Ошибка при запросе {url}: {e}")
            await asyncio.sleep(
                random.uniform(2, 5) * (attempt + 1)
            )  # Случайная задержка с ростом
        logger.error(f"Не удалось загрузить {url} после {retries} попыток.")
        return None

    async def parse_product(
        self, session: aiohttp.ClientSession, product_url: str, sem: asyncio.Semaphore
    ) -> Optional[Dict]:
        async with sem:
            content = await self.fetch(session, product_url)
            if not content:
                return None

            tree = html.fromstring(content)

            title = tree.xpath('//h1[@itemprop="name"]/text()')
            title = title[0].strip() if title else None
            if not title:
                return None

            images = tree.xpath('//img[@itemprop="image"]/@src')
            image = urljoin(BASE_URL, images[0]) if images else None

            brand = tree.xpath(
                '//a[contains(@class, "catalog-item--brand-title")]/text()'
            )
            brand = brand[0].strip() if brand else "Неизвестно"

            if brand not in WATCHES:
                for known_brand in WATCHES:
                    if known_brand.lower() in title.lower():
                        brand = known_brand
                        break
                else:
                    brand = "Неизвестно"

            price_text = tree.xpath('//p[contains(@class, "item-price--text")]/text()')
            # price = price_text[0].strip() if price_text else "Цена по запросу"
            if price_text:
                price_str = price_text[0].strip()
                digits = re.findall(r"\d+", price_str)
                if digits:
                    price = int("".join(digits))
                else:
                    price = "Цена по запросу"

            else:
                price = "Цена не найдена"

            city_elem = tree.xpath(
                '//div[contains(@class, "catalog-item--subinfo-item") and contains(@class, "d-flex") and contains(@class, "py-2")]//strong'
            )
            city = city_elem[0].text_content().strip() if city_elem else "Неизвестно"

            return {
                "name": title,
                "url": product_url,
                "image": image,
                "brand": brand,
                "price": price,
                "city": city,
            }

    async def parse_page(
        self, session: aiohttp.ClientSession, page_num: int
    ) -> List[str]:
        url = f"{BASE_URL}/clocks_today/?page={page_num}"
        logger.info(f"Загрузка страницы {page_num}: {url}")
        content = await self.fetch(session, url)
        if not content:
            return []

        tree = html.fromstring(content)
        links = tree.xpath(
            '//a[contains(@class, "product-list-item catalog-item")]/@href'
        )
        return [urljoin(BASE_URL, href) for href in links]

    async def main(self):
        start = time.time()
        connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT)
        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
        self.brand_cache = {}

        async with aiohttp.ClientSession(connector=connector) as session:
            page_num = 1
            while True:
                product_links = await self.parse_page(session, page_num)
                if not product_links:
                    logger.info("Нет товаров. Завершаем.")
                    break

                logger.info(
                    f"Найдено {len(product_links)} товаров на странице {page_num}"
                )

                tasks = [self.parse_product(session, url, sem) for url in product_links]
                products = await asyncio.gather(*tasks)
                products = [p for p in products if p]

                save_tasks = [self.save_product(p) for p in products]
                await asyncio.gather(*save_tasks)

                if len(product_links) < MAX_PRODUCTS_PER_PAGE:
                    break
                page_num += 1

        elapsed = time.time() - start
        self.stdout.write(
            self.style.SUCCESS(f"Импорт завершён за {timedelta(seconds=elapsed)}")
        )

    @sync_to_async
    def save_product(self, product_data: Dict):
        try:
            brand_slug = slugify(product_data["brand"])

            if brand_slug in self.brand_cache:
                brand = self.brand_cache[brand_slug]
            else:
                brand, _ = Brand.objects.get_or_create(
                    slug=brand_slug, defaults={"name": product_data["brand"]}
                )
                self.brand_cache[brand_slug] = brand

            product, _ = Product.objects.update_or_create(
                url=product_data["url"],
                defaults={
                    "title": product_data["name"],
                    "slug": slugify(product_data["name"]),
                    "brand": brand,
                    "image_url": product_data["image"],
                    "price_usd": (
                        float(product_data["price"])
                        if isinstance(product_data["price"], int)
                        else None
                    ),  # product_data['price'],
                },
            )
            # Обработка городов
            if product_data.get("city"):
                # Удаляем лишний текст "Наличие в городах:"
                city_str = product_data["city"].strip()

                # Разбиваем строку по запятым и фильтруем пустые значения
                city_names = [
                    name.strip() for name in city_str.split(",") if name.strip()
                ]

                city_objs = []
                for name in city_names:
                    # Удаляем возможные лишние пробелы и символы
                    clean_name = " ".join(name.split())
                    if clean_name:  # Проверяем, что название не пустое
                        city_obj, _ = City.objects.get_or_create(name=clean_name)
                        city_objs.append(city_obj)

                if city_objs:  # Обновляем связи только если есть города
                    product.cities.set(city_objs)

            logger.info(
                f"save: (id={product.id}) {product.title}"
                f"city: {', '.join(c.name for c in product.cities.all())}"
            )
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении товара {product_data.get('name', 'unknown')}: {e}",
                exc_info=True,
            )
