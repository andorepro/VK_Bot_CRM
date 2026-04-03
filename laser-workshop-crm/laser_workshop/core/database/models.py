# -*- coding: utf-8 -*-
"""
Модели базы данных для CRM системы лазерной мастерской
Поддержка станков: JPT M7 60W (оптоволоконный) и Ortur LM3 10W (диодный)
"""

import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    """Менеджер подключений к базе данных"""
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    def get_connection(self):
        """Получение подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей (админка)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'manager',
                permissions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица клиентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE,
                telegram_id INTEGER,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                cashback REAL DEFAULT 0.0,
                discount_percent REAL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица станков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                model TEXT NOT NULL,
                machine_type TEXT NOT NULL,
                power_watts REAL NOT NULL,
                work_area_width REAL,
                work_area_height REAL,
                max_speed REAL,
                status TEXT DEFAULT 'offline',
                current_job_id INTEGER,
                total_work_hours REAL DEFAULT 0.0,
                last_maintenance DATE,
                next_maintenance DATE,
                firmware_version TEXT,
                serial_number TEXT,
                location TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                client_id INTEGER NOT NULL,
                service_type TEXT NOT NULL,
                material_type TEXT,
                material_thickness REAL,
                design_file_path TEXT,
                preview_image_path TEXT,
                width_mm REAL,
                height_mm REAL,
                area_cm2 REAL,
                quantity INTEGER DEFAULT 1,
                complexity_level TEXT DEFAULT 'standard',
                machine_id INTEGER,
                assigned_operator_id INTEGER,
                setup_time_minutes INTEGER DEFAULT 0,
                work_time_minutes INTEGER DEFAULT 0,
                price_material REAL DEFAULT 0.0,
                price_work REAL DEFAULT 0.0,
                price_setup REAL DEFAULT 0.0,
                discount_percent REAL DEFAULT 0.0,
                final_price REAL,
                status TEXT DEFAULT 'new',
                priority TEXT DEFAULT 'normal',
                deadline DATE,
                comment TEXT,
                technical_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (machine_id) REFERENCES machines(id),
                FOREIGN KEY (assigned_operator_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица услуг и прайс-лист
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE,
                description TEXT,
                category TEXT,
                base_price_per_cm2 REAL NOT NULL,
                minimum_order_price REAL DEFAULT 300.0,
                setup_price REAL DEFAULT 150.0,
                recommended_machine_id INTEGER,
                max_material_thickness REAL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recommended_machine_id) REFERENCES machines(id)
            )
        ''')
        
        # Таблица материалов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                type TEXT,
                thickness_mm REAL,
                size_width_mm REAL,
                size_height_mm REAL,
                price_per_unit REAL,
                unit TEXT DEFAULT 'лист',
                stock_quantity INTEGER DEFAULT 0,
                min_stock_quantity INTEGER DEFAULT 5,
                supplier TEXT,
                compatible_machines TEXT,
                laser_absorption_rate REAL,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Журнал работы станков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machine_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                duration_seconds INTEGER,
                temperature REAL,
                power_percent REAL,
                speed_percent REAL,
                error_code TEXT,
                operator_id INTEGER,
                order_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id),
                FOREIGN KEY (operator_id) REFERENCES users(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        # Таблица складских остатков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                batch_number TEXT,
                quantity INTEGER DEFAULT 0,
                reserved_quantity INTEGER DEFAULT 0,
                location TEXT,
                purchase_date DATE,
                expiry_date DATE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        ''')
        
        # Таблица транзакций кэшбека
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cashback_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                order_id INTEGER,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                balance_after REAL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        # Таблица настроек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Индексы для ускорения поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_machine ON orders(machine_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_vk ON clients(vk_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_machine_logs_machine ON machine_logs(machine_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category)')
        
        conn.commit()
        
        # Добавление начальных данных для станков
        self._seed_initial_data(cursor)
        
        conn.commit()
        conn.close()
    
    def _seed_initial_data(self, cursor):
        """Добавление начальных данных"""
        
        # Проверка наличия станков
        cursor.execute('SELECT COUNT(*) FROM machines')
        if cursor.fetchone()[0] == 0:
            # JPT M7 60W - оптоволоконный маркер
            cursor.execute('''
                INSERT INTO machines (name, model, machine_type, power_watts, work_area_width, 
                                      work_area_height, max_speed, status, location, serial_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('JPT M7', 'M7 60W', 'fiber_marker', 60.0, 200.0, 200.0, 7000.0, 
                  'offline', 'Основной цех', 'JPT-M7-001'))
            
            # Ortur LM3 10W - диодный гравёр
            cursor.execute('''
                INSERT INTO machines (name, model, machine_type, power_watts, work_area_width, 
                                      work_area_height, max_speed, status, location, serial_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('Ortur LM3', 'LM3 10W', 'diode_engraver', 10.0, 400.0, 400.0, 10000.0, 
                  'offline', 'Основной цех', 'ORTUR-LM3-001'))
        
        # Проверка наличия услуг
        cursor.execute('SELECT COUNT(*) FROM services')
        if cursor.fetchone()[0] == 0:
            services = [
                ('Гравировка на металле', 'engrave_metal', 'Глубокая гравировка на металлических поверхностях', 
                 'engraving', 2.5, 300.0, 150.0, 1, 0.5),
                ('Маркировка металла', 'mark_metal', 'Поверхностная маркировка без углубления', 
                 'marking', 1.5, 250.0, 100.0, 1, 0.3),
                ('Гравировка на коже', 'engrave_leather', 'Художественная гравировка на кожаных изделиях', 
                 'engraving', 2.0, 300.0, 150.0, 2, None),
                ('Гравировка на дереве', 'engrave_wood', 'Гравировка на деревянных поверхностях', 
                 'engraving', 1.8, 250.0, 120.0, 2, 10.0),
                ('Резка фанеры', 'cut_plywood', 'Лазерная резка фанеры до 10мм', 
                 'cutting', 3.0, 400.0, 200.0, 2, 10.0),
                ('Гравировка на пластике', 'engrave_plastic', 'Гравировка на пластиковых изделиях', 
                 'engraving', 1.5, 250.0, 100.0, 2, 5.0),
                ('Гравировка на стекле', 'engrave_glass', 'Матирование стекла лазером', 
                 'engraving', 2.0, 350.0, 150.0, 2, None),
                ('Анодированный алюминий', 'engrave_anodized', 'Снятие слоя анодирования', 
                 'engraving', 1.8, 300.0, 120.0, 1, 0.2),
            ]
            for svc in services:
                cursor.execute('''
                    INSERT INTO services (name, code, description, category, base_price_per_cm2,
                                         minimum_order_price, setup_price, recommended_machine_id, 
                                         max_material_thickness)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', svc)
        
        # Проверка наличия материалов
        cursor.execute('SELECT COUNT(*) FROM materials')
        if cursor.fetchone()[0] == 0:
            materials = [
                ('Нержавеющая сталь', 'metal', 'steel', 2.0, 1000.0, 1000.0, 1500.0, 'лист', 10, 3,
                 'Поставщик 1', '1', 0.6, 'Для гравировки и маркировки'),
                ('Алюминий анодированный', 'metal', 'aluminum_anodized', 1.5, 1000.0, 1000.0, 1200.0, 'лист', 15, 3,
                 'Поставщик 1', '1', 0.7, 'Чёрный и цветной анод'),
                ('Кожа натуральная', 'leather', 'natural', 3.0, 500.0, 700.0, 800.0, 'лист', 20, 5,
                 'Поставщик 2', '2', 0.8, 'Разные цвета и фактуры'),
                ('Фанера берёзовая', 'wood', 'birch_plywood', 4.0, 1525.0, 1525.0, 600.0, 'лист', 30, 10,
                 'Поставщик 3', '2', 0.9, 'Сорт 1/1, 2/2'),
                ('Оргстекло акрил', 'plastic', 'acrylic', 3.0, 1600.0, 1000.0, 900.0, 'лист', 25, 5,
                 'Поставщик 3', '2', 0.5, 'Прозрачное и цветное'),
                ('Карта памяти пластик', 'plastic', 'abs_card', 2.0, 86.0, 54.0, 50.0, 'шт', 100, 20,
                 'Поставщик 4', '2', 0.6, 'Для брелоков и карт'),
            ]
            for mat in materials:
                cursor.execute('''
                    INSERT INTO materials (name, category, type, thickness_mm, size_width_mm,
                                          size_height_mm, price_per_unit, unit, stock_quantity,
                                          min_stock_quantity, supplier, compatible_machines,
                                          laser_absorption_rate, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', mat)
        
        # Начальные настройки
        settings = [
            ('cashback_percent', '5', 'Процент кэшбека от суммы заказа'),
            ('min_discount', '5', 'Минимальная скидка постоянным клиентам'),
            ('max_discount', '20', 'Максимальная скидка'),
            ('jpt_m7_hourly_rate', '1500', 'Стоимость часа работы JPT M7'),
            ('ortur_lm3_hourly_rate', '800', 'Стоимость часа работы Ortur LM3'),
            ('default_deadline_days', '3', 'Стандартный срок выполнения в днях'),
            ('urgent_multiplier', '1.5', 'Наценка за срочность'),
        ]
        for setting in settings:
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, description)
                VALUES (?, ?, ?)
            ''', setting)


# Глобальный экземпляр
db_manager = None


def get_db():
    """Получение подключения к БД"""
    from laser_workshop.core.config.settings import Settings
    settings = Settings()
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация БД"""
    from laser_workshop.core.config.settings import Settings
    settings = Settings()
    manager = DatabaseManager(settings.DB_PATH)
    manager.init_db()
