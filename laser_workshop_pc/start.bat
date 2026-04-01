@echo off
chcp 65001 > nul
echo ============================================
echo   Laser Workshop PC - Быстрый запуск
echo ============================================
echo.

REM Проверка Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

echo [OK] Python найден
echo.

REM Установка зависимостей (если нужно)
if not exist "venv" (
    echo [INFO] Создание виртуального окружения...
    python -m venv venv
)

echo [INFO] Активация виртуального окружения...
call venv\Scripts\activate.bat

echo [INFO] Проверка зависимостей...
pip install -q -r requirements.txt

echo.
echo ============================================
echo   Запуск сервера...
echo ============================================
echo.

REM Оптимизация Python для скорости
set PYTHONOPTIMIZE=1

REM Запуск основного приложения
start "Laser Workshop Server" cmd /k "python app.py"

REM Запуск бота (опционально, раскомментируйте если нужен VK бот)
REM start "VK Bot Worker" cmd /k "python bot_worker.py"

echo.
echo [OK] Сервер запущен!
echo.
echo +------------------------------------------+
echo |  Откройте браузер: http://localhost:5000 |
echo |  Логин: admin                            |
echo |  Пароль: admin123                        |
echo +------------------------------------------+
echo.
echo Нажмите Ctrl+C для остановки
pause
