# test_save_html.py
import asyncio
import sys
from loguru import logger
from playwright.async_api import async_playwright

# Настраиваем логирование
logger.remove()
logger.add(sys.stdout, level="DEBUG")

class TestParser:
    async def parse_product_page(self, url: str, browser):
        """Парсит страницу товара для получения детальной информации"""
        page = None
        context = None
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            
            # Переходим на страницу
            logger.debug(f"Переход на {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)  # Даем время на загрузку
            
            # Сохраняем HTML для анализа
            html = await page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML сохранен в debug_page.html")
            
            # Сохраняем скриншот для визуального анализа
            await page.screenshot(path='debug_screenshot.png', full_page=True)
            logger.info(f"Скриншот сохранен в debug_screenshot.png")
            
            data = {
                'city_name': '',
                'case_material': '',
                'water_resistance': '',
                'case_diameter': '',
                'strap_material': '',
                'movement_type': '',
                'glass': '',
                'dial_color': '',
                'bezel': '',
                'functions': '',
                'power_reserve': '',
                'caliber': '',
                'комплектация': '',
                'collection': '',
                'additional_images': [],
            }
            
            # ПАРСИНГОРОДА - проверим все возможные селекторы
            logger.debug("Поиск города...")
            
            # Получаем весь текст страницы для анализа
            page_text = await page.evaluate('document.body.innerText')
            logger.debug(f"Первые 500 символов текста страницы:\n{page_text[:500]}")
            
            # Ищем город по ключевым словам
            city_keywords = ['Москва', 'Санкт-Петербург', 'Казань', 'Екатеринбург', 
                           'Новосибирск', 'Нижний Новгород', 'Сочи', 'Краснодар']
            
            for city in city_keywords:
                if city in page_text:
                    data['city_name'] = city
                    logger.debug(f"✅ Найден город в тексте: {city}")
                    break
            
            # Также проверим селекторы
            city_selectors = [
                'div.catalog--subinfo strong',
                'div.catalog-item--subinfo strong',
                '.catalog-item__location',
                '.product-location',
                '.city',
                '[class*="city"]',
                '[class*="location"]',
                '[class*="address"]',
            ]
            
            for selector in city_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for i, elem in enumerate(elements):
                            text = await elem.text_content()
                            if text:
                                text = text.strip()
                                logger.debug(f"Селектор '{selector}' [{i}]: '{text}'")
                                if any(city in text for city in city_keywords):
                                    data['city_name'] = text
                                    logger.debug(f"✅ Город найден по селектору: {text}")
                except Exception as e:
                    pass
            
            # ПАРСИНГ ФОТОГРАФИЙ
            logger.debug("\nПоиск фотографий...")
            
            # Находим все изображения на странице
            all_images = await page.query_selector_all('img')
            logger.debug(f"Всего изображений на странице: {len(all_images)}")
            
            seen_urls = set()
            
            for i, img in enumerate(all_images):
                try:
                    # Пробуем получить src из разных атрибутов
                    src = None
                    for attr in ['src', 'data-src', 'data-lazy', 'data-original']:
                        src = await img.get_attribute(attr)
                        if src:
                            break
                    
                    if src:
                        # Преобразуем относительные URL
                        if src.startswith('/'):
                            src = 'https://lombard-perspectiva.ru' + src
                        
                        alt = await img.get_attribute('alt') or ''
                        img_class = await img.get_attribute('class') or ''
                        
                        logger.debug(f"Изображение {i+1}:")
                        logger.debug(f"  SRC: {src[:100]}...")
                        logger.debug(f"  ALT: {alt[:50]}")
                        logger.debug(f"  CLASS: {img_class[:50]}")
                        
                        # Проверяем, что это фото товара
                        if 'noimage' not in src.lower() and len(src) > 30:
                            if src not in seen_urls:
                                seen_urls.add(src)
                                # Если это не первое фото, добавляем в дополнительные
                                if len(seen_urls) > 1:
                                    data['additional_images'].append(src)
                except Exception as e:
                    logger.debug(f"Ошибка при обработке изображения {i}: {e}")
            
            # ПАРСИНГ ХАРАКТЕРИСТИК
            logger.debug("\nПоиск характеристик...")
            
            # Ищем все div с характеристиками
            char_rows = await page.query_selector_all('div.d-flex.flex-nowrap.justify-space-between.align-baseline')
            logger.debug(f"Найдено строк с характеристиками: {len(char_rows)}")
            
            for row in char_rows:
                try:
                    label_elem = await row.query_selector('div.option-label')
                    value_elem = await row.query_selector('div.option-value')
                    
                    if label_elem and value_elem:
                        label = await label_elem.text_content()
                        value = await value_elem.text_content()
                        
                        if label and value:
                            label = label.strip()
                            value = value.strip()
                            logger.debug(f"Характеристика: {label} = {value}")
                            
                            # Маппинг характеристик
                            if 'материал корпуса' in label.lower():
                                data['case_material'] = value
                            elif 'водонепроницаемость' in label.lower():
                                data['water_resistance'] = value
                            elif 'диаметр' in label.lower():
                                data['case_diameter'] = value
                            elif 'цвет циферблата' in label.lower():
                                data['dial_color'] = value
                            elif 'механизм' in label.lower():
                                data['movement_type'] = value
                            elif 'материал ремешка' in label.lower():
                                data['strap_material'] = value
                            elif 'стекло' in label.lower():
                                data['glass'] = value
                except Exception as e:
                    pass
            
            logger.debug(f"\n✅ Парсинг завершен. Найдено:")
            logger.debug(f"  Город: {data['city_name'] or 'не найден'}")
            logger.debug(f"  Доп. фото: {len(data['additional_images'])}")
            logger.debug(f"  Характеристики: {sum(1 for v in data.values() if v and v not in [data['city_name'], data['additional_images']])}")
            
            return data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return {}  # Возвращаем пустой словарь, а не None
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass

async def test_single_product():
    """Тест парсинга одного товара"""
    test_url = "https://lombard-perspectiva.ru/clock/rolex-submariner-116610lv-0002-26085730/"
    
    playwright = await async_playwright().start()
    
    # Запускаем браузер
    browser = await playwright.chromium.launch(
        headless=False,  # Видимый режим для отладки
        args=["--no-sandbox"]
    )
    
    try:
        parser = TestParser()
        result = await parser.parse_product_page(test_url, browser)
        
        print("\n" + "="*60)
        print("ИТОГОВЫЙ РЕЗУЛЬТАТ ПАРСИНГА:")
        print("="*60)
        
        if result:
            for key, value in result.items():
                if key == 'additional_images':
                    print(f"{key}: {len(value)} фото")
                    for i, img in enumerate(value[:3], 1):
                        print(f"  {i}. {img[:100]}...")
                elif value:
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: [не найдено]")
        else:
            print("❌ Не удалось получить данные")
        
        print("="*60)
        
        # Открываем браузер для ручного исследования
        input("\nНажмите Enter для закрытия браузера...")
        
    finally:
        await browser.close()
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(test_single_product())