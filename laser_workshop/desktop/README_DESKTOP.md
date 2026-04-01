# Лазерная Мастерская CRM - Версия для Windows Desktop

Полнофункциональная версия для запуска на настольных ПК и ноутбуках с Windows.

## Требования

- Windows 10/11
- Python 3.8 или выше
- Минимум 4GB RAM (рекомендуется 8GB+)
- Свободное место на диске: 500MB+

## Установка

### Вариант 1: Через PowerShell (рекомендуется)

```powershell
# Перейдите в папку проекта
cd laser_workshop\desktop

# Создайте виртуальное окружение
python -m venv venv

# Активируйте виртуальное окружение
.\venv\Scripts\Activate.ps1

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Запустите приложение
python app.py
```

### Вариант 2: Через Command Prompt

```cmd
cd laser_workshop\desktop
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

### Если скрипты PowerShell заблокированы

Выполните в PowerShell от имени администратора:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Автозапуск при загрузке Windows

### Способ 1: Через планировщик заданий

1. Откройте "Планировщик заданий" (Task Scheduler)
2. Создайте простую задачу:
   - Имя: `Laser Workshop CRM`
   - Триггер: "При входе в систему"
   - Действие: "Запустить программу"
   - Программа: `C:\path\to\laser_workshop\desktop\venv\Scripts\python.exe`
   - Аргументы: `app.py`
   - Рабочая папка: `C:\path\to\laser_workshop\desktop`

### Способ 2: Через ярлык в автозагрузке

1. Создайте файл `start_laser_workshop.bat`:

```batch
@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
python app.py
pause
```

2. Поместите ярлык этого файла в папку автозагрузки:
   - Нажмите `Win + R`
   - Введите: `shell:startup`
   - Перетащите ярлык в открывшуюся папку

## Запуск в фоновом режиме (как сервис)

Для запуска в фоновом режиме используйте NSSM (Non-Sucking Service Manager):

1. Скачайте NSSM: https://nssm.cc/download
2. Распакуйте и откройте командную строку от имени администратора
3. Выполните:

```cmd
nssm install LaserWorkshop
```

4. В GUI настройте:
   - Path: `C:\path\to\laser_workshop\desktop\venv\Scripts\python.exe`
   - Startup directory: `C:\path\to\laser_workshop\desktop`
   - Arguments: `app.py`

5. Установите сервис:
```cmd
nssm start LaserWorkshop
```

## Конфигурация

Отредактируйте переменные в `app.py`:

```python
SECRET_KEY = 'ваш_секретный_ключ'
VK_TOKEN = 'ваш_vk_токен'
VK_GROUP_ID = 'ваш_id_группы'
YOOKASSA_SECRET = 'ваш_секрет_юкасса'
CDEK_API_KEY = 'ваш_ключ_cdek'
```

## Доступ к приложению

После запуска откройте браузер:
- Локально: http://localhost:5000
- Для других устройств в сети: http://YOUR_IP:5000

Учётные данные по умолчанию:
- Логин: `admin`
- Пароль: `admin123`

## Запуск VK бота

Бот можно запустить отдельно или вместе с основным приложением:

```powershell
# В новом окне PowerShell
.\venv\Scripts\Activate.ps1
python bot_worker.py
```

## Структура папок Desktop

```
desktop/
├── app.py              # Основной сервер (полная версия)
├── bot_worker.py       # VK бот worker
├── requirements.txt    # Зависимости
├── workshop.db         # База данных
├── backups/            # Резервные копии
├── logs/               # Логи
└── start.bat           # Скрипт быстрого запуска
```

## Особенности Desktop версии

| Параметр | Desktop |
|----------|---------|
| MAX_CONNECTIONS | 10 |
| THREAD_POOL_SIZE | 5 |
| CACHE_TTL | 300 сек |
| MAX_USER_STATES | 1000 |
| AI_PROGNOSIS_ENABLED | True |
| DEBUG_MODE | Доступен |

## Решение проблем

### Ошибка "Python не найден"

Убедитесь, что Python установлен и добавлен в PATH:
1. Скачайте с https://python.org
2. При установке отметьте "Add Python to PATH"

### Ошибка доступа к порту 5000

Измените порт в app.py:
```python
app.run(host='0.0.0.0', port=8080, debug=True)
```

### Брандмауэр блокирует доступ

Разрешите доступ в брандмауэре Windows:
```powershell
New-NetFirewallRule -DisplayName "Laser Workshop" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

### Ошибки при установке зависимостей

Обновите pip и установите визуально:
```powershell
python -m pip install --upgrade pip
pip install Flask PyJWT requests Werkzeug
```

## Экспорт и резервное копирование

- Резервная копия БД: `/api/backup/download`
- Экспорт заказов CSV: `/api/export/csv`
- Папка backups автоматически создаётся в директории проекта

## Обновление

```powershell
.\venv\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
```

## Поддержка нескольких пользователей

Для работы нескольких операторов одновременно:
1. Создайте учётные записи через админ-панель
2. Настройте права доступа (roles: admin, manager, master)
3. Используйте разные браузеры или режим инкогнито для тестирования
