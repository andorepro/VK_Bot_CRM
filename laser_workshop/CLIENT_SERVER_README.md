# 🏭 Laser Workshop - Клиент-Серверная Архитектура

## 📊 Общая схема проекта

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ЛОКАЛЬНАЯ СЕТЬ (LAN)                           │
│                                                                     │
│  ┌──────────────────┐              ┌────────────────────────────┐  │
│  │  RASPBERRY PI 3  │              │   ПК / МОБИЛЬНЫЕ УСТРОЙСТВА │  │
│  │    (СЕРВЕР)      │              │        (КЛИЕНТЫ)           │  │
│  │                  │              │                            │  │
│  │  • Flask App     │  HTTP API    │  • laser_workshop_client   │  │
│  │  • SQLite DB     │  ◄────────►  │  • Web Interface (PWA)     │  │
│  │  • VK Bot        │  :5000       │  • Local Cache             │  │
│  │  • Порт: 5000    │  :5001       │  • Offline Mode            │  │
│  │                  │              │  • Порт: 5001              │  │
│  └──────────────────┘              └────────────────────────────┘  │
│         ▲                                      ▲                   │
│         │                                      │                   │
│         └────────── Internet ──────────────────┘                   │
│                    (VK API, Payments)                              │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Структура проектов

### 1. Сервер на Raspberry Pi (`laser_workshop/rpi/`)
```
rpi/
├── app.py              # Flask сервер (основной)
├── bot_worker.py       # VK бот (фоновый процесс)
├── config.py           # Конфигурация из .env
├── .env.example        # Шаблон конфигурации
├── requirements.txt    # Зависимости
├── install.sh          # Скрипт установки
├── workshop.db         # База данных SQLite
└── README_RPI.md       # Документация
```

**Параметры:**
- MAX_CONNECTIONS: 5
- THREAD_POOL_SIZE: 2
- CACHE_SIZE: 32MB
- AI_PROGNOSIS: OFF
- Порт: 5000

### 2. Клиент для ПК и мобильных (`laser_workshop_client/`)
```
laser_workshop_client/
├── app.py              # Flask клиент (лёгкий)
├── config.py           # Конфигурация из .env
├── .env.example        # Шаблон конфигурации
├── requirements.txt    # Зависимости
├── templates/
│   └── index.html      # PWA интерфейс
├── static/             # Статические файлы
└── README_CLIENT.md    # Документация
```

**Параметры:**
- MAX_CONNECTIONS: 3
- THREAD_POOL_SIZE: 2
- CACHE_SIZE: 16MB
- OFFLINE_MODE: Optional
- Порт: 5001

### 3. Desktop версия (автономная) (`laser_workshop/desktop/`)
```
desktop/
├── app.py              # Полнофункциональная версия
├── bot_worker.py       # VK бот
├── config.py           # Конфигурация
├── .env.example        # Шаблон
├── start.bat           # Запуск для Windows
└── README_DESKTOP.md   # Документация
```

**Параметры:**
- MAX_CONNECTIONS: 10
- THREAD_POOL_SIZE: 5
- CACHE_SIZE: 64MB
- AI_PROGNOSIS: ON
- Порт: 5000

## 🔧 Настройка сети

### Шаг 1: Настройка Raspberry Pi

1. **Узнать IP адрес RPi:**
```bash
hostname -I
# или
ip addr show wlan0  # для WiFi
ip addr show eth0   # для Ethernet
```

2. **Настроить статический IP (рекомендуется):**
```bash
sudo nano /etc/dhcpcd.conf
# Добавить:
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```

3. **Запустить сервер:**
```bash
cd /workspace/laser_workshop/rpi
cp .env.example .env
nano .env  # отредактировать настройки
pip install -r requirements.txt
python app.py
```

### Шаг 2: Настройка клиента на ПК

1. **Отредактировать конфиг:**
```bash
cd laser_workshop_client
cp .env.example .env
nano .env
```

2. **Указать IP сервера:**
```ini
SERVER_HOST=192.168.1.100  # IP вашего Raspberry Pi
SERVER_PORT=5000
PORT=5001
```

3. **Запустить клиент:**
```bash
pip install -r requirements.txt
python app.py
```

### Шаг 3: Проверка соединения

**С ПК проверить доступность RPi:**
```bash
# Windows
ping 192.168.1.100

# Linux/Mac
ping -c 4 192.168.1.100
```

**Проверить API сервера:**
```bash
curl http://192.168.1.100:5000/api/ping
```

## 🌐 Доступ с мобильных устройств

### iOS (Safari):
1. Открыть: `http://<IP_ПК>:5001` или `http://192.168.1.100:5000`
2. Нажать "Поделиться" → "На экран «Домой»"
3. Приложение появится на главном экране

### Android (Chrome):
1. Открыть: `http://<IP_ПК>:5001`
2. Меню → "Установить приложение"
3. Ярлык на рабочем столе

## 🔐 Безопасность

### 1. Изменить пароли по умолчанию:
```ini
# В .env файле
DEFAULT_ADMIN_PASSWORD=новый_сложный_пароль
SECRET_KEY=уникальная_секретная_строка
```

### 2. Настроить брандмауэр на RPi:
```bash
sudo ufw allow 5000/tcp
sudo ufw enable
```

### 3. Для продакшена использовать HTTPS:
```bash
# Установка SSL сертификата (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
```

## 📊 Поток данных

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   КЛИЕНТ    │      │   СЕРВЕР     │      │   БАЗА      │
│  (ПК/Phone) │      │  (Raspberry) │      │   ДАННЫХ    │
└──────┬──────┘      └──────┬───────┘      └──────┬──────┘
       │                    │                     │
       │ 1. GET /api/orders │                     │
       ├───────────────────►│                     │
       │                    │ 2. SELECT * FROM    │
       │                    ├────────────────────►│
       │                    │                     │
       │                    │ 3. Данные           │
       │                    ◄─────────────────────┤
       │                    │                     │
       │ 4. JSON ответ      │                     │
       ◄───────────────────┤                     │
       │                    │                     │
       │ 5. Кэширование     │                     │
       └────────┐           │                     │
                │           │                     │
       ┌────────┘           │                     │
       │ 6. Офлайн режим    │                     │
       │ (если нет связи)   │                     │
       └───────────────────►│                     │
                            │ 7. Очередь sync     │
                            └────────────────────►│
```

## 🔄 Синхронизация

### Автоматическая:
- Интервал: 30 секунд
- Проверка: `/api/ping`
- Отправка офлайн-операций

### Ручная:
```javascript
fetch('/api/sync', {method: 'POST'})
```

### Конфликты:
- Приоритет у сервера
- Локальные изменения помечаются timestamp
- Слияние по принципу "последняя запись"

## 📈 Мониторинг

### Проверка статуса сервера:
```bash
# На Raspberry Pi
systemctl status laser-workshop  # если через systemd
ps aux | grep python             # процессы
netstat -tlnp | grep 5000        # порты
```

### Логи:
```bash
# Сервер
tail -f /workspace/laser_workshop/rpi/logs/app.log

# Клиент
tail -f logs/client.log
```

## ⚡ Оптимизация производительности

### Для RPi:
```ini
# .env
MAX_CONNECTIONS=5
THREAD_POOL_SIZE=2
CACHE_SIZE_MB=32
AI_PROGNOSIS_ENABLED=False
```

### Для клиента:
```ini
# .env
CACHE_TTL_SECONDS=60
AUTO_SYNC=True
SYNC_INTERVAL_SECONDS=30
```

## 🐛 Решение проблем

| Проблема | Решение |
|----------|---------|
| "Server unavailable" | Проверить IP, ping, firewall |
| Клиент не видит сервер | Убедиться, что в одной сети |
| Медленная работа | Уменьшить CACHE_TTL, отключить AI |
| Офлайн режим застрял | Очистить client_cache.db |

## 📞 Поддержка

- Документация: README_*.md файлы
- Issues: GitHub repository
- Email: support@laserworkshop.local

---

**Версия:** 2.0 Client-Server  
**Дата:** 2026-01-24
