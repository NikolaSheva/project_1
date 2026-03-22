#!/bin/bash

# Убиваем старые процессы
pkill -f gunicorn 2>/dev/null || true
sleep 2

# Принудительно освобождаем порт
fuser -k 10000/tcp 2>/dev/null || true
sleep 2

echo "Starting gunicorn server..."
gunicorn your_project.wsgi:application \
    --bind 0.0.0.0:10000 \
    --workers 3 \
    --pid gunicorn.pid
