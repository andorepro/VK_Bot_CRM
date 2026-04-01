@echo off
REM Лазерная Мастерская CRM - Быстрый запуск для Windows Desktop
chcp 65001 >nul
echo ============================================================
echo    Лазерная Мастерская CRM - Запуск
echo ============================================================
echo.

cd /d "%~dp0"

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден! Установите Python 3.8+
    echo Скачайте с https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Создание venv если нет
if not exist venv (
    echo [*] Создание виртуального окружения...
    python -m venv venv
) else (
    echo [✓] Виртуальное окружение найдено
)

REM Активация
call venv\Scripts\activate.bat

REM Быстрая проверка зависимостей
echo [*] Проверка зависимостей...
pip show flask >nul 2>&1 && pip show pyjwt >nul 2>&1
if errorlevel 1 (
    echo [*] Установка зависимостей...
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
) else (
    echo [✓] Зависимости установлены
)

REM Создание директорий
if not exist backups mkdir backups
if not exist logs mkdir logs

echo.
echo ============================================================
echo    ✓ Готово к запуску!
echo ============================================================
echo.
echo Сервер запустится на: http://localhost:5000
echo Логин: admin | Пароль: admin123
echo.
echo Для остановки нажмите Ctrl+C
echo ============================================================
echo.

REM Запуск с оптимизацией
set PYTHONOPTIMIZE=1
python app.py

pause
