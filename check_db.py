import os
import django
from django.db import connection
from dotenv import load_dotenv
from pathlib import Path

# Загрузка .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Проверка DATABASE_URL
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL не найдена в .env")
else:
    print(f"✅ DATABASE_URL: {db_url}")

# Настройка Django окружения
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Попробуем подключиться к базе и выполнить SELECT 1
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        row = cursor.fetchone()
        print(f"✅ Успешное подключение. Ответ от базы данных: {row}")
except Exception as e:
    print(f"❌ Ошибка подключения к базе данных: {e}")