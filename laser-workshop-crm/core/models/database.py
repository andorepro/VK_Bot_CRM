"""
Модели базы данных
"""
import sqlite3
from datetime import datetime
from core.config import DB_PATH

def get_db_connection():
    """Получить соединение с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Клиенты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_orders INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            cashback_balance REAL DEFAULT 0,
            segment TEXT DEFAULT 'new'
        )
    ''')
    
    # Услуги и цены
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calc_type TEXT NOT NULL,
            base_price REAL NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Материалы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            price_per_unit REAL,
            unit TEXT,
            stock_quantity REAL DEFAULT 0,
            min_stock REAL DEFAULT 0
        )
    ''')
    
    # Заказы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            status TEXT DEFAULT 'new',
            priority TEXT DEFAULT 'normal',
            description TEXT,
            parameters TEXT,
            quantity INTEGER DEFAULT 1,
            unit_price REAL,
            total_price REAL,
            discount REAL DEFAULT 0,
            final_price REAL,
            machine_assigned TEXT,
            due_date TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # История изменений заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT,
            comment TEXT,
            changed_by TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')
    
    # Промокоды
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_percent REAL NOT NULL,
            max_uses INTEGER,
            current_uses INTEGER DEFAULT 0,
            valid_until TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Сообщения VK
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vk_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_message_id INTEGER UNIQUE,
            client_id INTEGER,
            text TEXT,
            attachments TEXT,
            from_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    # Настройки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT
        )
    ''')
    
    # Журнал работы станков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS machine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            order_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')
    
    # Индексы для ускорения поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_vk ON clients(vk_id)')
    
    # Начальные данные - услуги
    services_data = [
        ('Гравировка металла (JPT)', 'area_cm2', 15.0, 'Гравировка на металле, цена за см²'),
        ('Маркировка металла', 'fixed', 100.0, 'Фиксированная цена за маркировку'),
        ('Гравировка кожи', 'area_cm2', 12.0, 'Гравировка на коже, цена за см²'),
        ('Гравировка дерева', 'area_cm2', 10.0, 'Гравировка на дереве, цена за см²'),
        ('Резка фанеры до 10мм', 'meter_thickness', 25.0, 'Резка фанеры, цена за метр реза'),
        ('Гравировка колец/ручек', 'per_char', 5.0, 'Гравировка текста, цена за символ'),
        ('B2B тираж', 'setup_batch', 500.0, 'Настройка + цена за штуку'),
        ('Фото на металле', 'photo_raster', 20.0, 'Растровая гравировка фото'),
        ('Гравировка термосов', 'cylindrical', 18.0, 'Гравировка на цилиндрических объектах'),
        ('3D клише', 'volume_3d', 30.0, 'Объемная гравировка клише'),
        ('Комплекс: материал + резка', 'material_and_cut', 15.0, 'Материал и резка вместе')
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO services (name, calc_type, base_price, description) VALUES (?, ?, ?, ?)',
        services_data
    )
    
    # Начальные данные - материалы
    materials_data = [
        ('Нержавеющая сталь', 'metal', 0, 'шт', 100, 10),
        ('Алюминий анодированный', 'anodized_aluminum', 0, 'шт', 100, 10),
        ('Кожа натуральная', 'leather', 0, 'см²', 5000, 500),
        ('Фанера 4мм', 'wood', 50.0, 'лист', 50, 5),
        ('Фанера 6мм', 'wood', 70.0, 'лист', 50, 5),
        ('Фанера 10мм', 'wood', 100.0, 'лист', 30, 3),
        ('Акрил прозрачный', 'acrylic', 80.0, 'лист', 30, 3),
        ('Пластик ABS', 'plastic', 60.0, 'лист', 40, 5)
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO materials (name, type, price_per_unit, unit, stock_quantity, min_stock) VALUES (?, ?, ?, ?, ?, ?)',
        materials_data
    )
    
    # Начальные настройки
    settings_data = [
        ('vk_group_id', '0', 'ID группы VK'),
        ('cashback_percent', '5', 'Процент кэшбека'),
        ('auto_notifications', '1', 'Автоуведомления клиентам'),
        ('theme', 'dark', 'Тема интерфейса')
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)',
        settings_data
    )
    
    conn.commit()
    conn.close()
    print("✅ База данных успешно инициализирована")

if __name__ == '__main__':
    init_db()
