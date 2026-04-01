# Лазерная Мастерская CRM - Версия для Raspberry Pi 3 Model B+

Оптимизированная версия для запуска на Raspberry Pi 3 Model B+ с ограниченными ресурсами (1GB RAM, 4-core ARM Cortex-A53).

## Особенности оптимизации для RPi

- Уменьшен размер пула соединений БД (MAX_CONNECTIONS = 5)
- Уменьшен размер кэша (LRU_CACHE_MAX_SIZE = 50)
- Отключены тяжёлые AI прогнозы по умолчанию
- Уменьшен размер thread pool (THREAD_POOL_SIZE = 2)
- Оптимизированы настройки SQLite для ARM

## Установка

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install -y python3 python3-pip python3-venv sqlite3 git

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --no-cache-dir -r requirements.txt

# Запуск
python app.py
```

## Автозапуск при загрузке (systemd)

Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/laser-workshop.service
```

Содержимое:

```ini
[Unit]
Description=Laser Workshop CRM Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/laser_workshop/rpi
Environment="PATH=/home/pi/laser_workshop/rpi/venv/bin"
ExecStart=/home/pi/laser_workshop/rpi/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable laser-workshop.service
sudo systemctl start laser-workshop.service
sudo systemctl status laser-workshop.service
```

## Мониторинг ресурсов

```bash
# Проверка использования памяти
free -h

# Проверка температуры CPU
vcgencmd measure_temp

# Логи сервиса
journalctl -u laser-workshop.service -f
```

## Рекомендации для RPi

1. Используйте качественное охлаждение (радиатор + вентилятор)
2. Используйте быстрый microSD карту (Class 10, UHS-I) или SSD через USB
3. Отключите неиспользуемые интерфейсы в `/boot/config.txt`
4. Для продакшена рассмотрите использование gunicorn с 2 workers

## Запуск бота VK (опционально)

Бот можно запускать отдельно или вместе с основным приложением:

```bash
# В отдельном терминале
source venv/bin/activate
python bot_worker.py
```

Или добавьте второй сервис systemd для бота.

## Структура папок RPi

```
rpi/
├── app.py              # Ссылка на основной app.py
├── bot_worker.py       # Ссылка на bot_worker.py
├── requirements.txt    # Ссылка на требования
├── workshop.db         # База данных (создаётся автоматически)
├── backups/            # Резервные копии
└── logs/               # Логи (рекомендуется настроить)
```

## Отличия от desktop версии

| Параметр | Raspberry Pi | Desktop |
|----------|--------------|---------|
| MAX_CONNECTIONS | 5 | 10 |
| THREAD_POOL_SIZE | 2 | 5 |
| CACHE_TTL | 180 | 300 |
| MAX_USER_STATES | 500 | 1000 |
| AI_PROGNOSIS_ENABLED | False | True |
