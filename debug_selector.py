import asyncio
from playwright.async_api import async_playwright

async def debug_page(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print(f"Открываю страницу: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Сохраняем скриншот
        await page.screenshot(path="debug_screenshot.png")
        print("Скриншот сохранен как debug_screenshot.png")
        
        # ПРОВЕРКА СЕЛЕКТОРОВ
        print("\n" + "="*50)
        print("ПРОВЕРКА СЕЛЕКТОРОВ:")
        print("="*50)
        
        selectors = [
            ".catalog-item-photos_grid",
            ".catalog-item--photos__grid",
            "[class*='catalog-item-photos']",
            ".catalog-item-photos",
            ".gallery",
        ]
        
        for selector in selectors:
            elements = await page.locator(selector).count()
            print(f"Селектор '{selector}': найдено {elements} элементов")
        
        # ВСЕ ИЗОБРАЖЕНИЯ
        print("\n" + "="*50)
        print("ВСЕ ИЗОБРАЖЕНИЯ НА СТРАНИЦЕ:")
        print("="*50)
        
        all_images = await page.locator("img").all()
        print(f"Всего img тегов: {len(all_images)}")
        
        for i, img in enumerate(all_images[:15]):
            src = await img.get_attribute("src")
            classes = await img.get_attribute("class")
            print(f"\n{i+1}. src: {src}")
            print(f"   class: {classes}")
        
        # ИЩЕМ ИЗОБРАЖЕНИЯ В ГАЛЕРЕЕ
        print("\n" + "="*50)
        print("ИЗОБРАЖЕНИЯ В ГАЛЕРЕЕ .catalog-item--photos__grid:")
        print("="*50)
        
        gallery = page.locator(".catalog-item--photos__grid")
        if await gallery.count() > 0:
            print(f"✅ Галерея найдена!")
            
            gallery_images = await gallery.locator("img").all()
            print(f"Найдено {len(gallery_images)} изображений в галерее")
            
            # Собираем уникальные URL из галереи
            unique_urls = set()
            for i, img in enumerate(gallery_images):
                src = await img.get_attribute("src")
                if src:
                    if src.startswith('//'):
                        full_url = f"https:{src}"
                    elif src.startswith('/'):
                        full_url = f"https://lombard-perspectiva.ru{src}"
                    else:
                        full_url = src
                    unique_urls.add(full_url)
            
            # Выводим уникальные URL
            print(f"\nУникальных изображений в галерее: {len(unique_urls)}")
            for i, url in enumerate(sorted(unique_urls), 1):
                print(f"{i}. {url}")
        else:
            print("❌ Галерея не найдена")
        
        # ИЩЕМ ВСЕ preview-image
        print("\n" + "="*50)
        print("ИЗОБРАЖЕНИЯ С КЛАССОМ preview-image:")
        print("="*50)
        
        preview_images = await page.locator("img.preview-image").all()
        print(f"Найдено {len(preview_images)} preview-image")
        
        # Собираем уникальные URL preview-image
        unique_preview = set()
        for img in preview_images:
            src = await img.get_attribute("src")
            if src:
                if src.startswith('//'):
                    full_url = f"https:{src}"
                elif src.startswith('/'):
                    full_url = f"https://lombard-perspectiva.ru{src}"
                else:
                    full_url = src
                unique_preview.add(full_url)
        
        for i, url in enumerate(sorted(unique_preview), 1):
            print(f"{i}. {url}")
        
        # ОСНОВНОЕ ИЗОБРАЖЕНИЕ (ИСПРАВЛЕНО!)
        print("\n" + "="*50)
        print("ОСНОВНОЕ ИЗОБРАЖЕНИЕ:")
        print("="*50)
        
        # ИСПРАВЛЕНИЕ: .first - это свойство, его нельзя использовать с await
        main_img_element = page.locator("img.catalog-item-img--object").first
        if await main_img_element.count() > 0:
            src = await main_img_element.get_attribute("src")
            if src:
                if src.startswith('//'):
                    full_url = f"https:{src}"
                elif src.startswith('/'):
                    full_url = f"https://lombard-perspectiva.ru{src}"
                else:
                    full_url = src
                print(f"src: {full_url}")
            else:
                print("Основное изображение не найдено")
        else:
            print("Основное изображение не найдено")
        
        # ИТОГ: ВСЕ УНИКАЛЬНЫЕ ФОТО ТОВАРА
        print("\n" + "="*50)
        print("✅ ВСЕ УНИКАЛЬНЫЕ ФОТО ТОВАРА:")
        print("="*50)
        
        # Собираем все фото товара (исключая основное)
        all_product_photos = set()
        for img in gallery_images:
            src = await img.get_attribute("src")
            if src:
                if src.startswith('//'):
                    full_url = f"https:{src}"
                elif src.startswith('/'):
                    full_url = f"https://lombard-perspectiva.ru{src}"
                else:
                    full_url = src
                all_product_photos.add(full_url)
        
        # Исключаем основное фото
        if 'main_full_url' in locals():
            all_product_photos.discard(main_full_url)
        
        print(f"Найдено {len(all_product_photos)} уникальных дополнительных фото:")
        for i, url in enumerate(sorted(all_product_photos), 1):
            print(f"{i}. {url}")
        
        await browser.close()

if __name__ == "__main__":
    url = "https://lombard-perspectiva.ru/clock/patek-philippe--5077100g-079-12012200/"
    asyncio.run(debug_page(url))