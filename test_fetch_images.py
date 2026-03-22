import asyncio
import sys
from urllib.parse import urljoin
from playwright.async_api import async_playwright

BASE_URL = "https://lombard-perspectiva.ru"

async def test_extract_product_images(product_url: str):
    """Тестирует сбор фото со страницы товара"""
    print(f"\n🔍 Тестируем URL: {product_url}")
    print("="*60)
    
    images = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # Делаем видимым для отладки
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
            print("1️⃣ Загружаем страницу...")
            await page.goto(product_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Сохраняем скриншот для отладки
            await page.screenshot(path="debug_page.png")
            print("   ✅ Скриншот сохранен: debug_page.png")
            
            # 2. Ищем галерею
            print("\n2️⃣ Ищем галерею div.catalog-item--photos__grid...")
            gallery = page.locator("div.catalog-item--photos__grid")
            gallery_count = await gallery.count()
            print(f"   Найдено галерей: {gallery_count}")
            
            if gallery_count > 0:
                # Ищем все image_wrapper
                image_wrappers = await gallery.locator("div.image_wrapper").all()
                print(f"   Найдено image_wrapper: {len(image_wrappers)}")
                
                for idx, wrapper in enumerate(image_wrappers, 1):
                    img = wrapper.locator("img").first
                    if await img.count() > 0:
                        src = await img.get_attribute("src")
                        if src:
                            if src.startswith('//'):
                                full_url = f"https:{src}"
                            elif src.startswith('/'):
                                full_url = urljoin(BASE_URL, src)
                            else:
                                full_url = src
                            
                            if full_url not in images:
                                images.append(full_url)
                                print(f"   📸 Фото {idx}: {full_url}")
            
            # 3. Ищем preview-image (старый метод)
            print("\n3️⃣ Ищем по старым селекторам (preview-image)...")
            old_selectors = [
                "img.preview-image",
                ".product-gallery img",
                ".thumbnails img",
                ".gallery-thumbnails img",
                "[class*='thumbnail'] img",
                ".preview-images img",
                ".product-images img",
                ".swiper-slide img",
                "img[src*='/storage/']"
            ]
            
            for selector in old_selectors:
                elements = await page.locator(selector).all()
                if elements:
                    print(f"   Селектор '{selector}': найдено {len(elements)} элементов")
                    for elem in elements[:3]:  # Покажем первые 3
                        src = await elem.get_attribute("src")
                        if src:
                            print(f"     - {src[:50]}...")
            
            # 4. Основное фото
            print("\n4️⃣ Основное фото (img.catalog-item-img--object):")
            main_img = page.locator("img.catalog-item-img--object").first
            if await main_img.count() > 0:
                src = await main_img.get_attribute("src")
                if src:
                    if src.startswith('//'):
                        main_src = f"https:{src}"
                    elif src.startswith('/'):
                        main_src = urljoin(BASE_URL, src)
                    else:
                        main_src = src
                    print(f"   Основное фото: {main_src}")
                    
                    # Исключаем основное фото из списка
                    if main_src in images:
                        images.remove(main_src)
                        print(f"   ✅ Основное фото исключено из доп. фото")
            
            # 5. Итог
            print("\n" + "="*60)
            print(f"📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
            print(f"   Всего уникальных доп. фото: {len(images)}")
            if images:
                print(f"   Первые 5 фото:")
                for i, img in enumerate(images[:5], 1):
                    print(f"     {i}. {img}")
            else:
                print("   ❌ Дополнительные фото не найдены")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()
    
    return images

async def main():
    # URL для тестирования (можно передать как аргумент)
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://lombard-perspectiva.ru/clock/maurice-lacroix-masterpiece-mp7208-11033532/"
    
    await test_extract_product_images(url)

if __name__ == "__main__":
    asyncio.run(main())