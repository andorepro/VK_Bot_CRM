#!/bin/bash
echo "🚀 Запуск Лазерная Мастерская CRM..."
cd "$(dirname "$0")"

# Проверка .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env не найден. Создаю из шаблона..."
    cp .env.example .env
    echo "❗ Отредактируйте .env перед запуском!"
    exit 1
fi

# Создание папок
mkdir -p templates static backups certs

# Установка зависимостей
echo "📦 Установка зависимостей..."
pip install -r requirements.txt --quiet

# Генерация сертификатов если нужно
if [ ! -f "certs/cert.pem" ]; then
    echo "🔐 Генерация SSL сертификатов..."
    bash generate_certs.sh certs
fi

# Запуск
echo "🌐 Сервер: $(grep -q 'USE_HTTPS=True' .env 2>/dev/null && echo 'https' || echo 'http')://localhost:$(grep PORT .env | cut -d= -f2)"
echo "👤 Логин: admin | Пароль: $(grep DEFAULT_ADMIN_PASSWORD .env | cut -d= -f2)"
python3 app.py