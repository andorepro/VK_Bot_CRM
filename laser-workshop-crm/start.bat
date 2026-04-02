@echo off
echo 🚀 Запуск Лазерная Мастерская CRM...
cd /d "%~dp0"

:: Проверка .env
if not exist ".env" (
    echo ⚠️  .env не найден. Создаю из шаблона...
    copy .env.example .env
    echo ❗ Отредактируйте .env перед запуском!
    pause
    exit /b 1
)

:: Создание папок
if not exist "templates" mkdir templates
if not exist "static" mkdir static
if not exist "backups" mkdir backups
if not exist "certs" mkdir certs

:: Установка зависимостей
echo 📦 Установка зависимостей...
pip install -r requirements.txt --quiet

:: Генерация сертификатов если нужно
if not exist "certs\cert.pem" (
    echo 🔐 Генерация SSL сертификатов...
    bash generate_certs.sh certs
)

:: Запуск
echo 🌐 Сервер запущен на http://localhost:5000
echo 👤 Логин: admin | Пароль: %DEFAULT_ADMIN_PASSWORD%
python app.py
pause