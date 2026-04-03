# Лазерная Мастерская CRM

Система управления лазерной мастерской с поддержкой двух станков:
- **JPT M7 60W** — оптоволоконный лазерный маркер (металлы)
- **Ortur LM3 10W** — диодный гравёр (неметаллы)

> ⚠️ **Типы станков скрыты от клиентов** — система автоматически выбирает подходящее оборудование.

## 📁 Структура проекта

```
laser_workshop/
├── core/
│   ├── database/
│   │   ├── models.py       # Модели БД
│   │   └── init_db.py      # Инициализация данными
│   └── config/
│       └── database.py     # Конфигурация и подключение к БД
├── services/
│   ├── order_service.py    # Управление заказами
│   └── machine_service.py  # Управление станками
├── bot/                    # VK бот (в разработке)
│   ├── handlers/
│   ├── keyboards/
│   ├── middlewares/
│   └── states/
├── admin/                  # Админ-панель (в разработке)
│   ├── routes/
│   ├── forms/
│   └── templates/
└── utils/                  # Утилиты
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install sqlalchemy vkbot flask
```

### 2. Инициализация базы данных

```python
from laser_workshop.core.config.database import engine, SessionLocal
from laser_workshop.core.database.init_db import init_database
from laser_workshop.core.config.database import init_db_schema

# Создание таблиц
init_db_schema(engine)

# Заполнение начальными данными
db = SessionLocal()
init_database(db)
db.close()
```

### 3. Пример использования

```python
from laser_workshop.core.config.database import SessionLocal
from laser_workshop.services.order_service import OrderService
from laser_workshop.services.machine_service import MachineService

db = SessionLocal()

# Сервис заказов
order_svc = OrderService(db)

# Расчёт стоимости
price = order_svc.calculate_price(
    service_id=1,        # Гравировка металла
    area_cm2=50,         # 50 см²
    quantity=2,          # 2 изделия
    material_id=1        # Нержавеющая сталь
)
print(f"Стоимость: {price['total_amount']} руб.")
print(f"Кэшбек: {price['cashback']} руб.")

# Создание заказа
order = order_svc.create_order(
    client_id=1,
    service_id=1,
    area_cm2=50,
    quantity=2,
    description="Гравировка логотипа на брелоках"
)
print(f"Заказ #{order.id} создан!")
print(f"Станок назначен автоматически: {'Да' if order.assigned_machine_id else 'Нет'}")

# Сервис станков
machine_svc = MachineService(db)

# Статистика
stats = machine_svc.get_statistics()
print(f"Активных станков: {stats['active']}")
print(f"Всего наработано часов: {stats['total_work_hours']}")

db.close()
```

## 💰 Прайс-лист

| Услуга | Цена за см² | Мин. заказ | Станок (внутр.) |
|--------|-------------|------------|-----------------|
| Гравировка металла | 50 ₽ | 500 ₽ | fiber_marker |
| Маркировка металла | 30 ₽ | 400 ₽ | fiber_marker |
| Гравировка кожи | 40 ₽ | 350 ₽ | diode_engraver |
| Гравировка дерева | 35 ₽ | 350 ₽ | diode_engraver |
| Гравировка пластика | 30 ₽ | 300 ₽ | оба |
| Гравировка стекла | 45 ₽ | 400 ₽ | diode_engraver |
| Резка фанеры до 10мм | 15 ₽ | 500 ₽ | diode_engraver |
| Резка акрила до 5мм | 20 ₽ | 600 ₽ | diode_engraver |

## 🎁 Система лояльности

- **5% кэшбек** с каждого оплаченного заказа
- Кэшбек накапливается на балансе клиента
- Можно оплачивать до 50% заказа кэшбеком

## 🔧 API сервисов

### OrderService

| Метод | Описание |
|-------|----------|
| `create_order()` | Создать заказ с авторасчётом |
| `calculate_price()` | Рассчитать стоимость |
| `update_status()` | Обновить статус |
| `get_client_orders()` | История заказов клиента |
| `assign_to_machine()` | Назначить станок (админ) |

### MachineService

| Метод | Описание |
|-------|----------|
| `get_all_machines()` | Все станки |
| `log_job_start()` | Начало работы |
| `log_job_complete()` | Завершение работы |
| `get_statistics()` | Статистика по станкам |
| `set_maintenance_complete()` | Завершить ТО |

## 📊 Модель данных

### Основные таблицы:
- **machines** — станки (внутренний ресурс)
- **services** — услуги прайс-листа
- **materials** — материалы
- **clients** — клиенты
- **orders** — заказы
- **machine_logs** — журнал работы станков
- **order_logs** — история изменений заказов
- **stock** — склад материалов
- **cashback_transactions** — транзакции кэшбека
- **settings** — настройки системы

## 🔐 Настройки по умолчанию

| Параметр | Значение |
|----------|----------|
| Логин админа | `admin` |
| Пароль админа | `admin123` ⚠️ |
| Кэшбек | 5% |
| Мин. заказ | 300 ₽ |

> ⚠️ **Измените пароль администратора перед запуском в production!**

## 📝 Лицензия

MIT
