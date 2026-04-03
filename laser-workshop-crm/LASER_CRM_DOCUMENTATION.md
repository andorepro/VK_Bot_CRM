# Laser Workshop CRM — Полноценная система управления лазерной мастерской

## 📋 Описание

CRM-система для управления лазерной мастерской с поддержкой двух станков:
- **JPT M7 60W** — оптоволоконный лазерный маркер (металлы, анодированные поверхности)
- **Ortur LM3 10W** — диодный лазерный гравёр (дерево, кожа, пластик, стекло)

Система включает VK-бот для клиентов и веб-админку для операторов и администраторов.

---

## 🏗️ Архитектура проекта

```
laser-workshop-crm/
├── laser_workshop/
│   ├── bot/                    # VK бот
│   │   ├── handlers/           # Обработчики сообщений
│   │   ├── keyboards/          # Клавиатуры
│   │   ├── states/             # Состояния диалогов
│   │   └── middlewares/        # Промежуточное ПО
│   ├── admin/                  # Веб-админка (Flask)
│   │   ├── routes/             # Маршруты
│   │   ├── forms/              # Формы
│   │   ├── models/             # Модели админки
│   │   ├── templates/          # HTML шаблоны
│   │   └── static/             # CSS/JS
│   ├── core/                   # Ядро системы
│   │   ├── config/             # Конфигурация
│   │   ├── database/           # Модели БД
│   │   └── utils/              # Утилиты
│   └── services/               # Бизнес-сервисы
│       ├── machine_service.py  # Управление станками
│       ├── order_service.py    # Управление заказами
│       └── core_services.py    # Уведомления, платежи, аналитика
├── logs/                       # Логи приложения
├── backups/                    # Резервные копии БД
├── certs/                      # SSL сертификаты
├── static/                     # Статика админки
├── templates/                  # Шаблоны админки
├── workshop.db                 # База данных SQLite
├── requirements.txt            # Зависимости Python
├── start.sh / start.bat        # Скрипты запуска
└── systemd/                    # Systemd сервисы
```

---

## 🗄️ База данных

### Таблицы

#### `machines` — Станки
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID станка |
| name | TEXT | Название (JPT M7, Ortur LM3) |
| model | TEXT | Модель |
| machine_type | TEXT | fiber_marker / diode_engraver |
| power_watts | REAL | Мощность (60W / 10W) |
| work_area_width | REAL | Ширина рабочей области (мм) |
| work_area_height | REAL | Высота рабочей области (мм) |
| status | TEXT | offline/idle/working/paused/error/maintenance |
| total_work_hours | REAL | Наработка в часах |
| last_maintenance | DATE | Дата последнего ТО |
| next_maintenance | DATE | Дата следующего ТО |

#### `orders` — Заказы
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID заказа |
| order_number | TEXT | Номер заказа (YYMMDD-XXXX) |
| client_id | INTEGER | Ссылка на клиента |
| service_type | TEXT | Тип услуги |
| material_type | TEXT | Тип материала |
| material_thickness | REAL | Толщина материала (мм) |
| width_mm | REAL | Ширина изделия (мм) |
| height_mm | REAL | Высота изделия (мм) |
| area_cm2 | REAL | Площадь обработки (см²) |
| quantity | INTEGER | Количество |
| complexity_level | TEXT | simple/standard/complex/ultra |
| machine_id | INTEGER | Назначенный станок |
| assigned_operator_id | INTEGER | Оператор |
| setup_time_minutes | INTEGER | Время настройки |
| work_time_minutes | INTEGER | Время работы |
| price_material | REAL | Стоимость материала |
| price_work | REAL | Стоимость работы |
| price_setup | REAL | Стоимость настройки |
| final_price | REAL | Итоговая стоимость |
| status | TEXT | new/confirmed/in_progress/etc. |
| priority | TEXT | low/normal/high/urgent |
| deadline | DATE | Срок выполнения |

#### `services` — Услуги и прайс-лист
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID услуги |
| name | TEXT | Название |
| code | TEXT | Код (engrave_metal, cut_plywood) |
| base_price_per_cm2 | REAL | Цена за см² |
| minimum_order_price | REAL | Минимальный заказ |
| setup_price | REAL | Стоимость настройки |
| recommended_machine_id | INTEGER | Рекомендуемый станок |
| max_material_thickness | REAL | Макс. толщина материала |

#### `materials` — Материалы
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID материала |
| name | TEXT | Название |
| category | TEXT | metal/wood/leather/plastic/glass |
| type | TEXT | steel/aluminum_anodized/birch_plywood |
| thickness_mm | REAL | Толщина (мм) |
| stock_quantity | INTEGER | Количество на складе |
| min_stock_quantity | INTEGER | Мин. остаток для заказа |
| supplier | TEXT | Поставщик |
| compatible_machines | TEXT | Совместимые станки (1=JPT, 2=Ortur) |

#### `machine_logs` — Журнал работы станков
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID записи |
| machine_id | INTEGER | Станок |
| event_type | TEXT | job_start/job_complete/error/maintenance |
| message | TEXT | Сообщение |
| duration_seconds | INTEGER | Длительность |
| temperature | REAL | Температура |
| power_percent | REAL | Мощность лазера (%) |
| speed_percent | REAL | Скорость (%) |
| error_code | TEXT | Код ошибки |
| operator_id | INTEGER | Оператор |
| order_id | INTEGER | Заказ |

#### `clients` — Клиенты
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID клиента |
| vk_id | INTEGER | VK ID |
| telegram_id | INTEGER | Telegram ID |
| name | TEXT | Имя |
| phone | TEXT | Телефон |
| email | TEXT | Email |
| total_orders | INTEGER | Всего заказов |
| total_spent | REAL | Общая сумма |
| cashback | REAL | Баланс кэшбека |
| discount_percent | REAL | Персональная скидка (%) |

#### `cashback_transactions` — Транзакции кэшбека
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | ID транзакции |
| client_id | INTEGER | Клиент |
| order_id | INTEGER | Заказ |
| amount | REAL | Сумма |
| transaction_type | TEXT | earn/spend/cancel |
| balance_after | REAL | Баланс после операции |

#### `settings` — Настройки системы
| Ключ | Значение | Описание |
|------|----------|----------|
| cashback_percent | 5 | Процент кэшбека |
| jpt_m7_hourly_rate | 1500 | Ставка часа JPT M7 |
| ortur_lm3_hourly_rate | 800 | Ставка часа Ortur LM3 |
| default_deadline_days | 3 | Стандартный срок |
| urgent_multiplier | 1.5 | Наценка за срочность |

---

## 🔧 Сервисы

### MachineService — Управление станками

```python
from laser_workshop.services.machine_service import LaserMachineService

# Получить все станки
machines = machine_service.get_all_machines()

# Рекомендовать станок для услуги
machine = machine_service.recommend_machine_for_order('engrave_metal')

# Запустить работу
machine_service.start_job(machine_id=1, order_id=42, operator_id=5)

# Завершить работу
machine_service.complete_job(machine_id=1, order_id=42, 
                            work_time_minutes=25, operator_id=5)

# Получить статистику
stats = machine_service.get_machine_statistics(machine_id=1, days=30)

# Проверить необходимость ТО
due_machines = machine_service.get_maintenance_due_machines()
```

### OrderService — Управление заказами

```python
from laser_workshop.services.order_service import OrderService

# Создать заказ
order_id = order_service.create_order(
    client_id=1,
    service_type='engrave_metal',
    material_type='steel',
    material_thickness=2.0,
    width_mm=50,
    height_mm=50,
    quantity=2,
    complexity='standard'
)

# Назначить на станок
order_service.assign_to_machine(order_id=42, machine_id=1, operator_id=5)

# Обновить статус
order_service.update_order_status(order_id=42, status='in_progress')

# Завершить заказ
order_service.complete_order(order_id=42, work_time_minutes=25)

# Начислить кэшбек
order_service.apply_cashback(client_id=1, order_id=42)

# Получить статистику
stats = order_service.get_statistics(start_date, end_date)
```

---

## 💰 Автоматический расчёт стоимости

Формула расчёта:
```
Стоимость = Материал + Работа + Настройка

Работа = Площадь(см²) × Цена_за_см² × Коэффициент_сложности
Настройка = Базовая_ставка (150-200 руб.)

Минимальный заказ = 250-400 руб. (в зависимости от услуги)
```

### Примеры расчёта

| Услуга | Материал | Размер | Кол-во | Площадь | Цена |
|--------|----------|--------|--------|---------|------|
| Гравировка металла | Сталь 2мм | 50×50мм | 2 шт | 50 см² | 3275 руб. |
| Гравировка дерева | Фанера 4мм | 100×100мм | 1 шт | 100 см² | 430 руб. |
| Резка фанеры | Фанера 6мм | 200×150мм | 1 шт | 300 см² | 1100 руб. |

---

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
cd laser-workshop-crm
pip install -r requirements.txt
```

### 2. Инициализация базы данных
```bash
python3 -c "from laser_workshop.core.database.models import DatabaseManager; DatabaseManager('workshop.db').init_db()"
```

### 3. Запуск
```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

---

## 📊 Возможности системы

### Для клиентов (VK бот)
- ✅ Расчёт стоимости онлайн
- ✅ Оформление заказа
- ✅ Отслеживание статуса
- ✅ История заказов
- ✅ Кэшбек и скидки
- ✅ Уведомления о готовности

### Для операторов (Админка)
- ✅ Управление заказами (Kanban/Таблица)
- ✅ Назначение на станки
- ✅ Контроль сроков
- ✅ Журнал работы станков
- ✅ Управление материалами
- ✅ Отчётность и статистика

### Для администраторов
- ✅ Управление станками
- ✅ Настройка прайс-листа
- ✅ Управление пользователями
- ✅ Финансовая отчётность
- ✅ Настройка кэшбека и скидок
- ✅ Резервное копирование

---

## 🔐 Безопасность

- Хеширование паролей (bcrypt)
- JWT токены для API
- Ролевая модель (admin/operator/manager)
- Логирование всех действий
- HTTPS (SSL сертификаты)
- Регулярные бэкапы БД

---

## 📈 Планы развития

- [ ] Интеграция с ЮKassa для оплаты
- [ ] Интеграция со CDEK для доставки
- [ ] Мобильное приложение для операторов
- [ ] Прямое подключение к станкам (G-code)
- [ ] Генерация G-code из изображений
- [ ] Telegram бот (дополнительно к VK)
- [ ] Email уведомления
- [ ] SMS уведомления

---

## 📞 Контакты

Разработчик: Laser Workshop Team  
Версия: 1.0.0  
Лицензия: Proprietary
