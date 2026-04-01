# 🚀 Лазерная Мастерская CRM - Полное Руководство по Запуску

## 📋 Структура Проектов

```
/workspace/
├── laser_workshop/           # Основной проект
│   ├── rpi/                  # Сервер для Raspberry Pi
│   ├── desktop/              # Автономная версия для ПК
│   └── generate_certs.sh     # Скрипт генерации SSL
├── laser_workshop_client/    # Клиент для ПК/телефонов
└── laser_workshop_pc/        # Полная версия только для ПК
```

## 🔐 Шаг 1: Генерация SSL Сертификатов

### Для всех проектов выполните:

```bash
# Raspberry Pi (Сервер)
cd /workspace/laser_workshop/rpi
../generate_certs.sh certs

# Desktop версия
cd /workspace/laser_workshop/desktop
../generate_certs.sh certs

# Клиентская версия
cd /workspace/laser_workshop_client
./generate_certs.sh certs

# PC версия
cd /workspace/laser_workshop_pc
./generate_certs.sh certs
```

### Добавить сертификат в доверенные (Опционально, но рекомендуется):

**Windows (от администратора):**
```cmd
certutil -addstore -f root "certs\server.crt"
```

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/server.crt
```

**Linux (Ubuntu/Debian):**
```bash
sudo cp certs/server.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

## ⚙️ Шаг 2: Настройка Конфигурации

### Raspberry Pi (Сервер)
```bash
cd /workspace/laser_workshop/rpi
cp .env.example .env
nano .env  # Отредактируйте настройки
```

**Важные настройки для `.env`:**
```ini
HOST=0.0.0.0
PORT=5000
USE_HTTPS=True
CERT_FILE=certs/server.crt
KEY_FILE=certs/server.key
MAX_CONNECTIONS=5
THREAD_POOL_SIZE=2
AI_PROGNOSIS_ENABLED=False
DEFAULT_ADMIN_PASSWORD=admin123
```

### Клиент (ПК/Телефоны)
```bash
cd /workspace/laser_workshop_client
cp .env.example .env
nano .env
```

**Важные настройки для `.env`:**
```ini
HOST=0.0.0.0
PORT=5001
USE_HTTPS=True
CERT_FILE=certs/client.crt
KEY_FILE=certs/client.key
SERVER_HOST=192.168.1.100  # IP адрес Raspberry Pi
SERVER_PORT=5000
SERVER_PROTOCOL=https
VERIFY_SERVER_SSL=False
OFFLINE_MODE=False
AUTO_SYNC=True
```

### Desktop Версия
```bash
cd /workspace/laser_workshop/desktop
cp .env.example .env
nano .env
```

### PC Версия
```bash
cd /workspace/laser_workshop_pc
cp .env.example .env
nano .env
```

## 📦 Шаг 3: Установка Зависимостей

```bash
# Raspberry Pi
cd /workspace/laser_workshop/rpi
pip install -r requirements.txt

# Desktop
cd /workspace/laser_workshop/desktop
pip install -r requirements.txt

# Клиент
cd /workspace/laser_workshop_client
pip install -r requirements.txt

# PC версия
cd /workspace/laser_workshop_pc
pip install -r requirements.txt
```

## ▶️ Шаг 4: Запуск Приложений

### Вариант A: Клиент-Серверная Архитектура (Рекомендуется)

**1. Запуск сервера на Raspberry Pi:**
```bash
cd /workspace/laser_workshop/rpi
python app.py
```
Сервер запустится на `https://0.0.0.0:5000`

**2. Запуск клиента на ПК:**
```bash
cd /workspace/laser_workshop_client
python app.py
```
Клиент запустится на `https://localhost:5001`

**3. Доступ с телефонов:**
- Откройте браузер на телефоне
- Перейдите на `https://<IP_ПК>:5001` или `https://<IP_RPi>:5000`

### Вариант B: Автономная Desktop Версия

```bash
cd /workspace/laser_workshop/desktop
python app.py
```

### Вариант C: Полная PC Версия

```bash
cd /workspace/laser_workshop_pc
python app.py
```

## 🔧 Быстрый Старт (Все в одном)

```bash
# 1. Генерация сертификатов для всех проектов
cd /workspace/laser_workshop
./generate_certs.sh rpi/certs
./generate_certs.sh desktop/certs
./generate_certs.sh ../laser_workshop_client/certs
./generate_certs.sh ../laser_workshop_pc/certs

# 2. Создание .env файлов
cd rpi && cp .env.example .env && cd ..
cd desktop && cp .env.example .env && cd ..
cd ../laser_workshop_client && cp .env.example .env && cd ..
cd ../laser_workshop_pc && cp .env.example .env && cd ..

# 3. Установка зависимостей
pip install -r rpi/requirements.txt
pip install -r desktop/requirements.txt
pip install -r laser_workshop_client/requirements.txt
pip install -r laser_workshop_pc/requirements.txt

# 4. Запуск сервера RPi (в первом терминале)
cd rpi && python app.py

# 5. Запуск клиента (во втором терминале)
cd ../laser_workshop_client && python app.py
```

## 🌐 Доступ к Приложению

| Компонент | URL | Порт | HTTPS |
|-----------|-----|------|-------|
| RPi Сервер | https://<IP_RPi>:5000 | 5000 | ✅ |
| Клиент ПК | https://localhost:5001 | 5001 | ✅ |
| Desktop | https://localhost:5000 | 5000 | ✅ |
| PC Версия | https://localhost:5000 | 5000 | ✅ |

**По умолчанию:**
- Логин: `admin`
- Пароль: `admin123`

## 📱 Мобильный Доступ

1. Убедитесь, что телефон в той же сети Wi-Fi
2. Откройте браузер на телефоне
3. Перейдите на `https://<IP_ПК>:5001` или `https://<IP_RPi>:5000`
4. Примите самоподписанный сертификат
5. Добавьте на главный экран как PWA приложение

## 🔍 Диагностика

### Проверка работы сервера:
```bash
curl -k https://localhost:5000/api/status
```

### Проверка логов:
```bash
# Вывод приложения показывает статус запуска
# Ищите строки:
# 🔒 HTTPS: Enabled
# 🌐 Host: 0.0.0.0
# 🔌 Port: 5000
```

### Проблемы с SSL:
- Убедитесь, что сертификаты сгенерированы
- Проверьте пути в `.env` файле
- Добавьте сертификат в доверенные

### Проблемы с подключением клиента к серверу:
- Проверьте `SERVER_HOST` в `.env` клиента
- Убедитесь, что сервер запущен
- Проверьте брандмауэр (порт 5000 должен быть открыт)

## 🛡️ Безопасность

1. **Смените пароль администратора** в `.env`:
   ```ini
   DEFAULT_ADMIN_PASSWORD=your_secure_password
   ```

2. **Сгенерируйте уникальный SECRET_KEY**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Для продакшена** используйте настоящие SSL сертификаты (Let's Encrypt)

## 📊 Сравнение Версий

| Функция | RPi Сервер | Клиент | Desktop | PC |
|---------|------------|--------|---------|-----|
| База данных | ✅ Полная | ⚡ Кэш | ✅ Полная | ✅ Полная |
| VK Бот | ✅ | ❌ | ✅ | ✅ |
| AI Прогнозы | ❌ | ❌ | ✅ | ✅ |
| Офлайн режим | ❌ | ✅ | ❌ | ❌ |
| Мобильный UI | ✅ | ✅ | ⚠️ | ⚠️ |
| Потоки | 2 | 2 | 5 | 5 |
| Соединения БД | 5 | 3 | 10 | 10 |

---

**Готово!** 🎉 Приложение готово к работе с HTTPS защитой.
