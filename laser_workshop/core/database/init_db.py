"""
Инициализация базы данных и заполнение начальными данными.
Типы станков скрыты от клиентов - используются только внутри системы.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from laser_workshop.core.database.models import (
    Machine, Service, Material, Setting, Stock
)


def init_database(db: Session):
    """Инициализация БД начальными данными"""
    
    # === Станки (внутренний ресурс, не виден клиентам) ===
    machines_data = [
        {
            'name': 'JPT M7 60W',
            'type': 'fiber_marker',      # Оптоволоконный лазер для металлов
            'status': 'active',
            'total_work_hours': 0.0,
            'last_maintenance': datetime.utcnow(),
            'next_maintenance': datetime.utcnow() + timedelta(days=30)
        },
        {
            'name': 'Ortur LM3 10W',
            'type': 'diode_engraver',    # Диодный лазер для неметаллов
            'status': 'active',
            'total_work_hours': 0.0,
            'last_maintenance': datetime.utcnow(),
            'next_maintenance': datetime.utcnow() + timedelta(days=30)
        }
    ]

    for m_data in machines_data:
        existing = db.query(Machine).filter_by(name=m_data['name']).first()
        if not existing:
            machine = Machine(**m_data)
            db.add(machine)
            print(f"✓ Добавлен станок: {machine.name} ({machine.type})")

    # === Услуги ===
    services_data = [
        {
            'name': 'Гравировка металла',
            'description': 'Глубокая гравировка на металлических поверхностях',
            'base_price_per_cm2': 50.0,
            'min_order_price': 500.0,
            'compatible_machine_types': 'fiber_marker'
        },
        {
            'name': 'Маркировка металла',
            'description': 'Поверхностная маркировка (серийные номера, логотипы)',
            'base_price_per_cm2': 30.0,
            'min_order_price': 400.0,
            'compatible_machine_types': 'fiber_marker'
        },
        {
            'name': 'Гравировка кожи',
            'description': 'Гравировка на натуральной и искусственной коже',
            'base_price_per_cm2': 40.0,
            'min_order_price': 350.0,
            'compatible_machine_types': 'diode_engraver'
        },
        {
            'name': 'Гравировка дерева',
            'description': 'Художественная гравировка на деревянных поверхностях',
            'base_price_per_cm2': 35.0,
            'min_order_price': 350.0,
            'compatible_machine_types': 'diode_engraver'
        },
        {
            'name': 'Гравировка пластика',
            'description': 'Гравировка на пластиковых изделиях',
            'base_price_per_cm2': 30.0,
            'min_order_price': 300.0,
            'compatible_machine_types': 'diode_engraver;fiber_marker'
        },
        {
            'name': 'Гравировка стекла',
            'description': 'Матовая гравировка на стекле и зеркалах',
            'base_price_per_cm2': 45.0,
            'min_order_price': 400.0,
            'compatible_machine_types': 'diode_engraver'
        },
        {
            'name': 'Резка фанеры до 10мм',
            'description': 'Лазерная резка фанеры толщиной до 10мм',
            'base_price_per_cm2': 15.0,
            'min_order_price': 500.0,
            'compatible_machine_types': 'diode_engraver'
        },
        {
            'name': 'Резка акрила до 5мм',
            'description': 'Лазерная резка акрилового листа',
            'base_price_per_cm2': 20.0,
            'min_order_price': 600.0,
            'compatible_machine_types': 'diode_engraver'
        }
    ]

    for s_data in services_data:
        existing = db.query(Service).filter_by(name=s_data['name']).first()
        if not existing:
            service = Service(**s_data)
            db.add(service)
            print(f"✓ Добавлена услуга: {service.name} ({service.base_price_per_cm2} руб/см²)")

    # === Материалы ===
    materials_data = [
        {'name': 'Нержавеющая сталь', 'category': 'metal', 'max_thickness_mm': 5.0, 'price_modifier': 1.0},
        {'name': 'Алюминий анодированный', 'category': 'metal', 'max_thickness_mm': 3.0, 'price_modifier': 1.2},
        {'name': 'Кожа натуральная', 'category': 'leather', 'max_thickness_mm': 10.0, 'price_modifier': 1.0},
        {'name': 'Фанера берёзовая', 'category': 'wood', 'max_thickness_mm': 10.0, 'price_modifier': 0.8},
        {'name': 'Акрил прозрачный', 'category': 'plastic', 'max_thickness_mm': 5.0, 'price_modifier': 1.1},
        {'name': 'Пластик ABS', 'category': 'plastic', 'max_thickness_mm': 3.0, 'price_modifier': 1.0},
        {'name': 'Стекло обычное', 'category': 'glass', 'max_thickness_mm': 10.0, 'price_modifier': 1.3},
        {'name': 'Заготовка клиента', 'category': 'other', 'max_thickness_mm': None, 'price_modifier': 1.0}
    ]

    for m_data in materials_data:
        existing = db.query(Material).filter_by(name=m_data['name']).first()
        if not existing:
            material = Material(**m_data)
            db.add(material)
            print(f"✓ Добавлен материал: {material.name}")

    # === Склад (начальные запасы) ===
    stock_data = [
        {'material_name': 'Фанера берёзовая', 'quantity': 50.0, 'unit': 'листов'},
        {'material_name': 'Акрил прозрачный', 'quantity': 20.0, 'unit': 'листов'},
        {'material_name': 'Кожа натуральная', 'quantity': 10.0, 'unit': 'м²'}
    ]

    for st_data in stock_data:
        material = db.query(Material).filter_by(name=st_data['material_name']).first()
        if material:
            existing = db.query(Stock).filter_by(material_id=material.id).first()
            if not existing:
                stock = Stock(
                    material_id=material.id,
                    quantity=st_data['quantity'],
                    unit=st_data['unit'],
                    min_level=5.0
                )
                db.add(stock)
                print(f"✓ Добавлено на склад: {st_data['material_name']} - {st_data['quantity']} {st_data['unit']}")

    # === Настройки ===
    settings_data = [
        {'key': 'cashback_percent', 'value': '5', 'description': 'Процент кэшбека'},
        {'key': 'min_order_price', 'value': '300', 'description': 'Минимальная стоимость заказа'},
        {'key': 'bot_token', 'value': '', 'description': 'Токен VK бота'},
        {'key': 'admin_login', 'value': 'admin', 'description': 'Логин администратора'},
        {'key': 'admin_password', 'value': 'admin123', 'description': 'Пароль администратора (изменить!)'},
        {'key': 'work_hours', 'value': '10:00-20:00', 'description': 'Часы работы'},
        {'key': 'contact_phone', 'value': '+7 (999) 000-00-00', 'description': 'Контактный телефон'},
        {'key': 'contact_address', 'value': 'г. Москва, ул. Примерная, д.1', 'description': 'Адрес мастерской'}
    ]

    for s_data in settings_data:
        existing = db.query(Setting).filter_by(key=s_data['key']).first()
        if not existing:
            setting = Setting(**s_data)
            db.add(setting)
            print(f"✓ Добавлена настройка: {s_data['key']}")

    db.commit()
    print("\n✅ База данных успешно инициализирована!")
