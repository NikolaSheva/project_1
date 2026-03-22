import asyncio
from playwright.async_api import async_playwright

async def check_model_extraction(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print(f"🔍 Открываю страницу: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Сохраняем скриншот для отладки
        await page.screenshot(path="debug_model.png")
        print("📸 Скриншот сохранен как debug_model.png")
        
        print("\n" + "="*50)
        print("🔍 ПРОВЕРКА ПАРСИНГА МОДЕЛИ")
        print("="*50)
        
        # 1. ПРОВЕРЯЕМ СЕЛЕКТОР, КОТОРЫЙ МЫ ИСПОЛЬЗУЕМ В ПАРСЕРЕ
        print("\n1️⃣ Селектор из парсера: p[title].text.text-xl-small.text-light.ma-0")
        model_elem = page.locator("p[title].text.text-xl-small.text-light.ma-0").first
        if await model_elem.count() > 0:
            model_text = await model_elem.text_content()
            model_title = await model_elem.get_attribute("title")
            print(f"✅ Найдено!")
            print(f"   text_content: {model_text}")
            print(f"   title атрибут: {model_title}")
        else:
            print("❌ Элемент не найден")
        
        # 2. ИЩЕМ ВСЕ ЭЛЕМЕНТЫ С АТРИБУТОМ TITLE
        print("\n2️⃣ Элементы с атрибутом title:")
        title_elements = await page.locator("[title]").all()
        print(f"Найдено элементов с title: {len(title_elements)}")
        for i, el in enumerate(title_elements[:5]):
            title = await el.get_attribute("title")
            text = await el.text_content()
            tag = await el.evaluate("el => el.tagName")
            print(f"   {i+1}. <{tag}> title='{title}' | text='{text}'")
        
        # 3. ИЩЕМ ЭЛЕМЕНТЫ ПО КЛАССАМ
        print("\n3️⃣ Поиск по классам:")
        class_selectors = [
            ".catalog-item--subtitle p",
            ".catalog-item--subtitle",
            "[class*='model']",
            ".product-model",
            ".model"
        ]
        
        for selector in class_selectors:
            elements = await page.locator(selector).all()
            if elements:
                print(f"\nСелектор '{selector}': найдено {len(elements)} элементов")
                for i, el in enumerate(elements[:3]):
                    text = await el.text_content()
                    classes = await el.get_attribute("class")
                    print(f"   {i+1}. класс: {classes}")
                    print(f"      текст: {text.strip() if text else ''}")
        
        # 4. ИЩЕМ КАРТОЧКУ ТОВАРА НА ГЛАВНОЙ
        print("\n" + "="*50)
        print("🔍 ПРОВЕРКА НА ГЛАВНОЙ СТРАНИЦЕ КАТАЛОГА")
        print("="*50)
        
        catalog_url = "https://lombard-perspectiva.ru/clocks_today/"
        await page.goto(catalog_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Ищем первую карточку товара
        first_card = page.locator("a[href^='/clock/']").first
        if await first_card.count() > 0:
            # Пробуем найти модель в карточке
            model_selectors = [
                "p[title].text.text-xl-small.text-light.ma-0",
                ".catalog-item--subtitle p",
                ".catalog-item--subtitle",
                "[class*='model']"
            ]
            
            print("\nВ первой карточке товара:")
            for selector in model_selectors:
                elem = first_card.locator(selector).first
                if await elem.count() > 0:
                    text = await elem.text_content()
                    title = await elem.get_attribute("title")
                    print(f"\n✅ Селектор '{selector}':")
                    print(f"   текст: {text.strip() if text else ''}")
                    if title:
                        print(f"   title: {title}")
            
            # Сохраняем HTML карточки для анализа
            card_html = await first_card.evaluate("el => el.outerHTML")
            with open("card_debug.html", "w") as f:
                f.write(card_html)
            print("\n📄 HTML карточки сохранен в card_debug.html")
        
        await browser.close()

if __name__ == "__main__":
    url = "https://lombard-perspectiva.ru/clock/jaeger-lecoultre-master-control-1602420-06042123/"
    asyncio.run(check_model_extraction(url))