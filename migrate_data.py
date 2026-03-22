import sqlite3
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from watch.models import Product, Brand

# Подключаемся к старой базе
old_db_path = '/home/sheva/mydata/pwatch/backup-20260305.sqlite3'
old_conn = sqlite3.connect(old_db_path)
old_conn.row_factory = sqlite3.Row
cursor = old_conn.cursor()

# Получаем все записи
cursor.execute("SELECT * FROM watches_watch")
rows = cursor.fetchall()
print(f"Найдено записей: {len(rows)}")

# Создаем бренд по умолчанию, если нет
default_brand, _ = Brand.objects.get_or_create(name="Другие")

imported = 0
for row in rows:
    try:
        # Пытаемся определить бренд из title
        title = row['title']
        brand_name = title.split()[0] if title else "Другие"
        brand, _ = Brand.objects.get_or_create(name=brand_name)
        
        # Создаем продукт
        product = Product(
            brand=brand,
            model=row['model'] or '',
            ref=row['ref'] or '',
            price_usd=row['price'] or 0,
            url=row['url'] or '',
            image_url=row['img'] or '',
            # Другие поля оставляем пустыми, так как их нет в старой базе
        )
        product.save()
        imported += 1
        if imported % 100 == 0:
            print(f"Импортировано: {imported}")
    except Exception as e:
        print(f"Ошибка при импорте {row['id']}: {e}")

print(f"Импортировано товаров: {imported}")
old_conn.close()