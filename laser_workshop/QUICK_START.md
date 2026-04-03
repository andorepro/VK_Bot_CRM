# ⚡ Быстрый Старт - Лазерная Мастерская CRM

## 🎯 5 Минут до Запуска

### Шаг 1: Генерация сертификатов (30 сек)
```bash
cd /workspace/laser_workshop
./generate_certs.sh rpi/certs
./generate_certs.sh desktop/certs  
./generate_certs.sh ../laser_workshop_client/certs
./generate_certs.sh ../laser_workshop_pc/certs
```

### Шаг 2: Создание конфигов (30 сек)
```bash
cd rpi && cp .env.example .env && cd ..
cd desktop && cp .env.example .env && cd ..
cd ../laser_workshop_client && cp .env.example .env && cd ..
cd ../laser_workshop_pc && cp .env.example .env && cd ..
```

### Шаг 3: Установка зависимостей (2 мин)
```bash
pip install -r rpi/requirements.txt
pip install -r desktop/requirements.txt
pip install -r laser_workshop_client/requirements.txt
pip install -r laser_workshop_pc/requirements.txt
```

### Шаг 4: Запуск (1 мин)

**Вариант A: Сервер + Клиент (RPi + ПК)**
```bash
# Терминал 1 - Сервер RPi
cd /workspace/laser_workshop/rpi
python app.py

# Терминал 2 - Клиент ПК
cd /workspace/laser_workshop_client
python app.py
```

**Вариант B: Только ПК (Desktop)**
```bash
cd /workspace/laser_workshop/desktop
python app.py
```

**Вариант C: Полная PC версия**
```bash
cd /workspace/laser_workshop_pc
python app.py
```

## ✅ Готово!

Откройте браузер:
- **HTTPS:** https://localhost:5000 (или :5001 для клиента)
- **Логин:** admin
- **Пароль:** admin123

## 📱 С Телефона

1. Узнайте IP компьютера: `ipconfig` (Windows) или `ifconfig` (Linux/Mac)
2. Откройте в браузере телефона: `https://<IP>:5001`
3. Примите сертификат безопасности
4. Добавьте на главный экран

## 🔧 Если что-то не работает

| Проблема | Решение |
|----------|---------|
| Ошибка SSL | Запустите `generate_certs.sh` ещё раз |
| Порт занят | Измените PORT в `.env` |
| Не подключается клиент | Проверьте SERVER_HOST в `.env` клиента |
| Ошибка импорта | `pip install -r requirements.txt` |

## 📚 Полная документация

См. [`README_SETUP.md`](README_SETUP.md) для подробной инструкции.
