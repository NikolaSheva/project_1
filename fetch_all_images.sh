#!/bin/bash
# fetch_all_images.sh

echo "🚀 Запуск сбора фото для всех товаров"
total_processed=0
batch_size=300

while [ $total_processed -lt 3000 ]; do
    echo ""
    echo "📦 Пакет $((total_processed / batch_size + 1)): обрабатываем товары $((total_processed + 1))-$((total_processed + batch_size))"
    echo "=========================================="
    
    python manage.py fetch_watch_images --limit $batch_size
    
    total_processed=$((total_processed + batch_size))
    echo "✅ Обработано всего: $total_processed товаров"
    
    # Пауза между пакетами, чтобы не нагружать сервер
    echo "⏳ Пауза 5 секунд..."
    sleep 5
done

echo ""
echo "🎉 ГОТОВО! Обработано $total_processed товаров"