#!/bin/bash
echo "Останавливаю Django сервер..."
pkill -9 -f "python.*manage.py runserver" 2>/dev/null
pkill -9 -f gunicorn
sleep 4

echo "Запускаю Django сервер..."
cd /home/sheva/mydata/project_1
# Активируем виртуальное окружение
source .venv/bin/activate
# Запускаем Django
#gunicorn config.wsgi:application -c gunicorn.conf.py
python manage.py runserver 10000 --settings=config.settings