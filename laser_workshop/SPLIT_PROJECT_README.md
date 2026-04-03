# Разделение проекта laser_workshop для Raspberry Pi и Windows Desktop

## Структура проекта

```
laser_workshop/
├── app.py                  # Оригинальная полная версия (источник)
├── bot_worker.py           # VK бот worker (общий)
├── requirements.txt        # Общие зависимости
├── static/                 # Статические файлы (CSS, JS)
├── templates/              # HTML шаблоны
├── tests/                  # Тесты
│
├── rpi/                    # Версия для Raspberry Pi 3 Model B+
│   ├── app.py              # Оптимизированная версия (меньше ресурсов)
│   ├── bot_worker.py       # Копия bot_worker.py
│   ├── requirements.txt    # Копия requirements.txt
│   ├── README_RPI.md       # Инструкция по установке и настройке
│   ├── install.sh          # Скрипт автоматической установки
│   ├── backups/            # Резервные копии БД
│   └── logs/               # Логи
│
└── desktop/                # Версия для Windows Desktop
    ├── app.py              # Полнофункциональная версия (все функции)
    ├── bot_worker.py       # Копия bot_worker.py
    ├── requirements.txt    # Копия requirements.txt
    ├── README_DESKTOP.md   # Инструкция по установке и настройке
    ├── start.bat           # Скрипт быстрого запуска
    ├── backups/            # Резервные копии БД
    └── logs/               # Логи
```

## Сравнение версий

| Параметр | Raspberry Pi | Windows Desktop |
|----------|--------------|-----------------|
| MAX_CONNECTIONS | 5 | 10 |
| THREAD_POOL_SIZE | 2 | 5 |
| CACHE_TTL | 180 сек | 300 сек |
| MAX_USER_STATES | 500 | 1000 |
| AI_PROGNOSIS_ENABLED | ❌ Отключено | ✅ Включено |
| DEBUG_MODE | ❌ Отключен | ✅ Включен |
| SQLite cache_size | 32MB | 64MB |
| static_url_path | ../static | ../static |

## Быстрый старт

### Raspberry Pi 3 Model B+

```bash
cd /home/pi/laser_workshop/rpi
chmod +x install.sh
./install.sh

# После установки:
source venv/bin/activate
python app.py
```

**Доступ:** http://raspberrypi.local:5000 или http://<IP_адрес_RPi>:5000

### Windows Desktop

```cmd
cd laser_workshop\desktop
start.bat
```

Или вручную:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

**Доступ:** http://localhost:5000

## Учётные данные по умолчанию

- **Логин:** `admin`
- **Пароль:** `admin123`

## Синхронизация изменений

При обновлении основного `app.py`:

1. Скопируйте изменения в `rpi/app.py` с сохранением оптимизаций
2. Скопируйте изменения в `desktop/app.py` с сохранением полного функционала
3. Протестируйте на обеих платформах

## Рекомендации по развёртыванию

### Для Raspberry Pi:
- Используйте SSD вместо microSD карты для лучшей надёжности
- Настройте охлаждение (радиаторы + вентилятор)
- Отключите неиспользуемые интерфейсы (Bluetooth, WiFi если не нужен)
- Настройте мониторинг температуры

### Для Windows Desktop:
- Добавьте в исключения антивируса папку проекта
- Настройте автозапуск через Планировщик заданий
- Регулярно делайте резервные копии БД
- Используйте источник бесперебойного питания

## Обновление зависимостей

### RPi:
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Desktop:
```powershell
.\venv\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
```

## Резервное копирование

База данных автоматически сохраняется в:
- `rpi/backups/`
- `desktop/backups/`

Ручное создание резервной копии:
```bash
# Linux/RPi
cp workshop.db backups/workshop_$(date +%Y%m%d).db

# Windows PowerShell
Copy-Item workshop.db backups/workshop_$(Get-Date -Format yyyyMMdd).db
```

## Поддержка

При возникновении проблем:
1. Проверьте логи в папке `logs/`
2. Убедитесь, что порты не заняты другими приложениями
3. Проверьте права доступа к файлам
4. Перезапустите сервис/приложение
