FROM python:3.11-slim
# предотвращает создание .pyc файлов
ENV PYTHONDONTWRITEBYTECODE=1
# отключает буферизацию вывода Python
ENV PYTHONUNBUFFERED=1
# Важные переменные окружения # Дополнительно: отключаем кеш pip
ENV PIP_NO_CACHE_DIR=1
WORKDIR /django_app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
# Установка зависимостей
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN python -m pip install uv && \
    uv pip install --system --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .
# Команда для запуска сервера
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
