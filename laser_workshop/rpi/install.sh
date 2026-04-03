#!/bin/bash
# Лазерная Мастерская CRM - Быстрая установка для Raspberry Pi

echo "============================================================"
echo "   Лазерная Мастерская CRM - Установка на Raspberry Pi"
echo "============================================================"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "[*] Установка Python..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv sqlite3
else
    echo "[✓] Python уже установлен"
fi

# Создание виртуального окружения (если нет)
if [ ! -d "venv" ]; then
    echo "[*] Создание виртуального окружения..."
    python3 -m venv venv
else
    echo "[✓] Виртуальное окружение уже существует"
fi

# Активация и установка зависимостей
echo "[*] Установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install --no-cache-dir -r requirements.txt --quiet

# Создание директорий
mkdir -p backups logs static templates

echo ""
echo "============================================================"
echo "   ✓ Установка завершена!"
echo "============================================================"
echo ""
echo "Быстрый запуск:"
echo "  source venv/bin/activate && python app.py"
echo ""
echo "Или через systemd:"
echo "  sudo systemctl enable laser-workshop"
echo "  sudo systemctl start laser-workshop"
echo ""
