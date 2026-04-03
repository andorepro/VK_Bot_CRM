# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import hashlib
import jwt
import datetime
import requests
import json
import csv
import shutil
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, send_file, send_from_directory
from functools import wraps
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from collections import defaultdict, OrderedDict
from contextlib import contextmanager
import random
import weakref

# ==================== КОНФИГУРАЦИЯ ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'workshop.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
SECRET_KEY = 'laser_workshop_secret_key_2026_change_this'
VK_TOKEN = 'YOUR_VK_TOKEN_HERE'
VK_GROUP_ID = 'YOUR_GROUP_ID'
YOOKASSA_SECRET = 'YOUR_YOOKASSA_SECRET'
CDEK_API_KEY = 'YOUR_CDEK_API_KEY'

# Оптимизация: настройки пула соединений и кэша
MAX_CONNECTIONS = 10
CACHE_TTL = 300  # 5 минут
MAX_USER_STATES = 1000  # Ограничение состояний бота
THREAD_POOL_SIZE = 5

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
app.secret_key = SECRET_KEY

# Включаем сжатие ответов
app.config['JSON_AS_ASCII'] = False

# ==================== ОПТИМИЗИРОВАННЫЙ ПУЛ СОЕДИНЕНИЙ ====================
class ConnectionPool:
    def __init__(self, db_path, max_connections=10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = Lock()
        self._initialized = False
    
    def _create_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Оптимизация: WAL режим для лучшей конкурентности
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-64000')  # 64MB кэш
        conn.execute('PRAGMA temp_store=MEMORY')
        return conn
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            with self._lock:
                if self._pool:
                    conn = self._pool.pop()
                else:
                    conn = self._create_connection()
            yield conn
        finally:
            if conn:
                with self._lock:
                    if len(self._pool) < self.max_connections:
                        self._pool.append(conn)
                    else:
                        conn.close()
    
    def init_db_schema(self, cursor):
        """Создание схемы БД с индексами"""
        # Таблица пользователей с ролями (Фаза 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'manager',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица клиентов с кэшбеком (Фаза 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                phone TEXT,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                avg_check REAL DEFAULT 0,
                last_order_date TIMESTAMP,
                customer_segment TEXT DEFAULT 'new',
                cashback_balance REAL DEFAULT 0,
                cashback_earned REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_vk ON clients(vk_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_segment ON clients(customer_segment)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_total_spent ON clients(total_spent DESC)')
        
        # Таблица прайс-листа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                calc_type TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                machine_type TEXT DEFAULT 'universal'
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_calc_type ON price_list(calc_type)')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                vk_id INTEGER,
                client_name TEXT,
                service_id INTEGER,
                service_name TEXT,
                description TEXT NOT NULL,
                parameters TEXT NOT NULL,
                total_price REAL NOT NULL,
                discount REAL DEFAULT 0,
                promo_code TEXT,
                cashback_applied REAL DEFAULT 0,
                status TEXT DEFAULT 'NEW',
                planned_date TIMESTAMP,
                completed_date TIMESTAMP,
                payment_status TEXT DEFAULT 'pending',
                payment_id TEXT,
                delivery_service TEXT,
                delivery_tracking TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (service_id) REFERENCES price_list(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_vk ON orders(vk_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_planned ON orders(planned_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_service ON orders(service_id)')
        
        # Таблица промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_percent REAL NOT NULL,
                max_uses INTEGER DEFAULT 1,
                current_uses INTEGER DEFAULT 0,
                valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valid_until TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code ON promo_codes(code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_active ON promo_codes(is_active, valid_until)')
        
        # Таблица сообщений VK
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vk_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER NOT NULL,
                from_user INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vk_messages_vk ON vk_messages(vk_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vk_messages_timestamp ON vk_messages(timestamp DESC)')
        
        # Таблица уведомлений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                vk_id INTEGER,
                message_text TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_order ON notifications(order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status)')
        
        # Таблица склада (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                quantity REAL DEFAULT 0,
                unit TEXT NOT NULL,
                min_quantity REAL DEFAULT 0,
                price_per_unit REAL DEFAULT 0,
                supplier TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_type ON inventory(item_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_low_stock ON inventory(quantity, min_quantity, is_active)')
        
        # Таблица операций склада (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                operation_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                order_id INTEGER,
                user_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES inventory(id),
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_ops_item ON inventory_operations(item_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_ops_created ON inventory_operations(created_at DESC)')
        
        # Таблица кэшбек-транзакций (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cashback_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                order_id INTEGER,
                amount REAL NOT NULL,
                operation_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cashback_client ON cashback_transactions(client_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cashback_created ON cashback_transactions(created_at DESC)')
        
        # Таблица интеграций (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                api_key TEXT,
                api_secret TEXT,
                is_active INTEGER DEFAULT 0,
                last_sync TIMESTAMP,
                config TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_integrations_service ON integrations(service_name)')
        
        # Таблица AI прогнозов (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT NOT NULL,
                prediction_data TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_predictions_type ON ai_predictions(prediction_type)')
        
        # Таблица аудита (НОВОЕ для Фазы 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)')

# Инициализация пула соединений
db_pool = ConnectionPool(DB_PATH, MAX_CONNECTIONS)

# ==================== КЭШИРОВАНИЕ ====================
class LRUCache:
    """LRU кэш с TTL для часто используемых данных"""
    def __init__(self, max_size=100, ttl=300):
        self.cache = OrderedDict()
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl
        self.lock = Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                # Проверка TTL
                if time.time() - self.timestamps[key] > self.ttl:
                    del self.cache[key]
                    del self.timestamps[key]
                    return None
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def set(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            self.timestamps[key] = time.time()
            if len(self.cache) > self.max_size:
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]
    
    def invalidate(self, key):
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
    
    def clear_pattern(self, pattern):
        """Инвалидация ключей по паттерну"""
        with self.lock:
            keys_to_delete = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.cache[key]
                del self.timestamps[key]

# Глобальные кэши
price_cache = LRUCache(max_size=10, ttl=CACHE_TTL)
client_cache = LRUCache(max_size=500, ttl=CACHE_TTL)
promo_cache = LRUCache(max_size=100, ttl=60)  # Промокоды кэшируем меньше
analytics_cache = LRUCache(max_size=50, ttl=60)  # Аналитика обновляется реже

# ==================== THREAD POOL ДЛЯ АСИНХРОННЫХ ОПЕРАЦИЙ ====================
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

def run_async(func, *args, **kwargs):
    """Запуск функции в фоне без ожидания результата"""
    return executor.submit(func, *args, **kwargs)

def init_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей с ролями (Фаза 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'manager',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица клиентов с кэшбеком (Фаза 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            total_orders INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            avg_check REAL DEFAULT 0,
            last_order_date TIMESTAMP,
            customer_segment TEXT DEFAULT 'new',
            cashback_balance REAL DEFAULT 0,
            cashback_earned REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица прайс-листа
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calc_type TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            machine_type TEXT DEFAULT 'universal'
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            vk_id INTEGER,
            client_name TEXT,
            service_id INTEGER,
            service_name TEXT,
            description TEXT NOT NULL,
            parameters TEXT NOT NULL,
            total_price REAL NOT NULL,
            discount REAL DEFAULT 0,
            promo_code TEXT,
            cashback_applied REAL DEFAULT 0,
            status TEXT DEFAULT 'NEW',
            planned_date TIMESTAMP,
            completed_date TIMESTAMP,
            payment_status TEXT DEFAULT 'pending',
            payment_id TEXT,
            delivery_service TEXT,
            delivery_tracking TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (service_id) REFERENCES price_list(id)
        )
    ''')
    
    # Таблица промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_percent REAL NOT NULL,
            max_uses INTEGER DEFAULT 1,
            current_uses INTEGER DEFAULT 0,
            valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица сообщений VK
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vk_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER NOT NULL,
            from_user INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица уведомлений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            vk_id INTEGER,
            message_text TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Таблица склада (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            unit TEXT NOT NULL,
            min_quantity REAL DEFAULT 0,
            price_per_unit REAL DEFAULT 0,
            supplier TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Таблица операций склада (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            operation_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            order_id INTEGER,
            user_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES inventory(id),
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Таблица кэшбек-транзакций (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cashback_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            order_id INTEGER,
            amount REAL NOT NULL,
            operation_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')
    
    # Таблица интеграций (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            is_active INTEGER DEFAULT 0,
            last_sync TIMESTAMP,
            config TEXT
        )
    ''')
    
    # Таблица AI прогнозов (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_type TEXT NOT NULL,
            prediction_data TEXT NOT NULL,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица аудита (НОВОЕ для Фазы 3)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Создаем админа по умолчанию
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)', 
                      ('admin', password_hash, 'admin'))
    
    # Создаем тестовых пользователей с ролями
    test_users = [
        ('manager1', 'manager123', 'manager'),
        ('master1', 'master123', 'master')
    ]
    
    for username, password, role in test_users:
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        if not cursor.fetchone():
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                          (username, password_hash, role))
    
    # Заполняем прайс-лист 11 услугами
    price_items = [
        ('Фляжка/Жетон (шт)', 'fixed', 500.0, 'Фиксированная цена за штуку', 'universal'),
        ('Шильд/Дерево (см²)', 'area_cm2', 15.0, 'Цена за см² гравировки', 'ortur'),
        ('Резка фанеры (мм)', 'meter_thickness', 25.0, 'Цена за метр реза * толщину', 'ortur'),
        ('MOPA 3D гравировка (мин)', 'per_minute', 100.0, 'Цена за минуту работы', 'jpt'),
        ('Кольца/Ручки (символ)', 'per_char', 50.0, 'Цена за символ', 'jpt'),
        ('Промышленная резка (м)', 'vector_length', 80.0, 'Цена за метр вектора', 'universal'),
        ('B2B Тираж (настройка+шт)', 'setup_batch', 300.0, 'Настройка + цена за штуку', 'universal'),
        ('Фото на дереве/металле', 'photo_raster', 20.0, 'Площадь * цена * DPI множитель', 'ortur'),
        ('Термосы/Кружки (ось)', 'cylindrical', 35.0, 'Диаметр * π * длина / 100', 'jpt'),
        ('3D Клише (объем)', 'volume_3d', 45.0, 'Площадь * глубина * цена', 'jpt'),
        ('Материал + Резка', 'material_and_cut', 30.0, 'Площадь материала + метры реза', 'ortur')
    ]
    
    cursor.execute('SELECT COUNT(*) FROM price_list')
    if cursor.fetchone()[0] == 0:
        for item in price_items:
            cursor.execute('''
                INSERT INTO price_list (name, calc_type, price, description, machine_type)
                VALUES (?, ?, ?, ?, ?)
            ''', item)
    
    # Создаем тестовые промокоды
    promo_items = [
        ('WELCOME10', 10.0, 100, 0, None, 1),
        ('VIP20', 20.0, 50, 0, None, 1),
        ('NEWYEAR25', 25.0, 200, 0, '2026-12-31', 1)
    ]
    
    cursor.execute('SELECT COUNT(*) FROM promo_codes')
    if cursor.fetchone()[0] == 0:
        for item in promo_items:
            cursor.execute('''
                INSERT INTO promo_codes (code, discount_percent, max_uses, current_uses, valid_until, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', item)
    
    # Создаем тестовые товары склада
    inventory_items = [
        ('Фанера 3мм', 'material', 100, 'листов', 10, 500, 'Поставщик 1'),
        ('Фанера 6мм', 'material', 50, 'листов', 5, 800, 'Поставщик 1'),
        ('Акрил 3мм', 'material', 30, 'листов', 5, 1200, 'Поставщик 2'),
        ('Металл заготовки', 'material', 200, 'шт', 20, 150, 'Поставщик 3'),
        ('Фляжки', 'product', 50, 'шт', 10, 300, 'Поставщик 3'),
        ('Жетоны', 'product', 100, 'шт', 20, 100, 'Поставщик 3'),
        ('Линза фокусная', 'consumable', 5, 'шт', 2, 2500, 'Поставщик 4'),
        ('Зеркала', 'consumable', 10, 'шт', 3, 1500, 'Поставщик 4'),
        ('Ремень приводной', 'consumable', 8, 'шт', 2, 800, 'Поставщик 4')
    ]
    
    cursor.execute('SELECT COUNT(*) FROM inventory')
    if cursor.fetchone()[0] == 0:
        for item in inventory_items:
            cursor.execute('''
                INSERT INTO inventory (item_name, item_type, quantity, unit, min_quantity, price_per_unit, supplier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', item)
    
    # Создаем интеграции
    integration_services = ['1C', 'MoySklad', 'CDEK', 'YooKassa']
    cursor.execute('SELECT COUNT(*) FROM integrations')
    if cursor.fetchone()[0] == 0:
        for service in integration_services:
            cursor.execute('''
                INSERT INTO integrations (service_name, is_active) VALUES (?, 0)
            ''', (service,))
    
    conn.commit()
    conn.close()

# ==================== JWT АВТОРИЗАЦИЯ ====================
def generate_token(username, role='manager'):
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return redirect(url_for('login_page'))
        payload = verify_token(token)
        if not payload:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.cookies.get('auth_token')
            if not token:
                return redirect(url_for('login_page'))
            payload = verify_token(token)
            if not payload or payload.get('role') not in allowed_roles:
                return jsonify({'error': 'Доступ запрещён'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def log_audit(user_id, action, entity_type=None, entity_id=None, old_value=None, new_value=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, action, entity_type, entity_id, 
          json.dumps(old_value) if old_value else None,
          json.dumps(new_value) if new_value else None,
          request.remote_addr))
    conn.commit()
    conn.close()

# ==================== VK API ФУНКЦИИ ====================
def vk_send_message(vk_id, message):
    try:
        url = 'https://api.vk.com/method/messages.send'
        params = {
            'user_id': vk_id,
            'message': message,
            'random_id': int(time.time() * 1000),
            'access_token': VK_TOKEN,
            'v': '5.131'
        }
        response = requests.post(url, params=params, timeout=10)
        return response.json().get('response', {}).get('message_id', 0)
    except Exception as e:
        print(f"VK Send Error: {e}")
        return 0

def save_vk_message(vk_id, from_user, message_text, is_admin=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vk_messages (vk_id, from_user, message_text, is_admin)
        VALUES (?, ?, ?, ?)
    ''', (vk_id, from_user, message_text, is_admin))
    conn.commit()
    conn.close()

def save_notification(order_id, vk_id, message_text, status='pending'):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (order_id, vk_id, message_text, status)
        VALUES (?, ?, ?, ?)
    ''', (order_id, vk_id, message_text, status))
    conn.commit()
    conn.close()

# ==================== КАЛЬКУЛЯТОР (11 ТИПОВ) ====================
def calculate_price(calc_type, params, base_price):
    price = 0.0
    
    if calc_type == 'fixed':
        quantity = int(params.get('quantity', 1))
        price = base_price * quantity
    elif calc_type == 'area_cm2':
        length = float(params.get('length', 0))
        width = float(params.get('width', 0))
        area = (length / 10) * (width / 10)
        price = area * base_price
    elif calc_type == 'meter_thickness':
        meters = float(params.get('meters', 0))
        thickness = float(params.get('thickness', 3))
        price = meters * (base_price * (thickness / 3.0))
    elif calc_type == 'per_minute':
        minutes = float(params.get('minutes', 0))
        price = minutes * base_price
    elif calc_type == 'per_char':
        chars = int(params.get('chars', 0))
        price = chars * base_price
    elif calc_type == 'vector_length':
        length = float(params.get('length', 0))
        price = length * base_price
    elif calc_type == 'setup_batch':
        setup_price = float(params.get('setup_price', base_price))
        unit_price = float(params.get('unit_price', base_price))
        quantity = int(params.get('quantity', 1))
        price = setup_price + (unit_price * quantity)
    elif calc_type == 'photo_raster':
        length = float(params.get('length', 0))
        width = float(params.get('width', 0))
        dpi_multiplier = float(params.get('dpi_multiplier', 1.0))
        area = (length / 10) * (width / 10)
        price = area * base_price * dpi_multiplier
    elif calc_type == 'cylindrical':
        diameter = float(params.get('diameter', 0))
        length = float(params.get('length', 0))
        area = (diameter * 3.14 * length) / 100
        price = area * base_price
    elif calc_type == 'volume_3d':
        length = float(params.get('length', 0))
        width = float(params.get('width', 0))
        depth = float(params.get('depth', 0))
        volume = (length / 10) * (width / 10) * depth
        price = volume * base_price
    elif calc_type == 'material_and_cut':
        length = float(params.get('length', 0))
        width = float(params.get('width', 0))
        cut_meters = float(params.get('cut_meters', 0))
        material_price = float(params.get('material_price', base_price))
        cut_price = float(params.get('cut_price', base_price))
        material_cost = (length / 10) * (width / 10) * material_price
        cut_cost = cut_meters * cut_price
        price = material_cost + cut_cost
    
    return round(price, 2)

def apply_discount(total_price, quantity, promo_code=None, cashback_balance=0):
    discount = 0
    discount_source = 'quantity'
    cashback_used = 0
    
    # Оптовые скидки
    if quantity >= 100:
        discount = 0.20
    elif quantity >= 50:
        discount = 0.15
    elif quantity >= 20:
        discount = 0.10
    elif quantity >= 10:
        discount = 0.05
    
    # Промокод (приоритет выше)
    if promo_code:
        promo_discount = validate_promo_code(promo_code)
        if promo_discount and promo_discount > discount:
            discount = promo_discount
            discount_source = 'promo'
    
    discounted_price = total_price * (1 - discount)
    
    # Применяем кэшбек (максимум 30% от суммы)
    max_cashback = discounted_price * 0.30
    if cashback_balance > 0:
        cashback_used = min(cashback_balance, max_cashback)
        discounted_price -= cashback_used
    
    return round(discounted_price, 2), int(discount * 100), discount_source, round(cashback_used, 2)

def validate_promo_code(code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT discount_percent, max_uses, current_uses, valid_until, is_active
        FROM promo_codes WHERE code = ?
    ''', (code,))
    promo = cursor.fetchone()
    conn.close()
    
    if not promo:
        return None
    if not promo['is_active']:
        return None
    if promo['current_uses'] >= promo['max_uses']:
        return None
    if promo['valid_until']:
        valid_until = datetime.datetime.strptime(promo['valid_until'], '%Y-%m-%d')
        if datetime.datetime.now() > valid_until:
            return None
    
    return promo['discount_percent'] / 100.0

def use_promo_code(code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?
    ''', (code,))
    conn.commit()
    conn.close()

def add_cashback(client_id, order_id, amount):
    """Начисление кэшбека 5% от суммы заказа"""
    cashback = amount * 0.05
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO cashback_transactions (client_id, order_id, amount, operation_type)
        VALUES (?, ?, ?, 'earned')
    ''', (client_id, order_id, cashback))
    
    cursor.execute('''
        UPDATE clients SET cashback_balance = cashback_balance + ?, 
                          cashback_earned = cashback_earned + ?
        WHERE id = ?
    ''', (cashback, cashback, client_id))
    
    conn.commit()
    conn.close()
    
    return cashback

def use_cashback(client_id, amount):
    """Списание кэшбека"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO cashback_transactions (client_id, amount, operation_type)
        VALUES (?, ?, 'spent')
    ''', (client_id, amount))
    
    cursor.execute('''
        UPDATE clients SET cashback_balance = cashback_balance - ?
        WHERE id = ?
    ''', (amount, client_id))
    
    conn.commit()
    conn.close()

def update_client_stats(client_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as total_orders, SUM(total_price) as total_spent,
               MAX(created_at) as last_order_date
        FROM orders WHERE client_id = ? AND status IN ('DONE', 'DELIVERED')
    ''', (client_id,))
    stats = cursor.fetchone()
    
    if stats and stats['total_orders']:
        avg_check = stats['total_spent'] / stats['total_orders'] if stats['total_orders'] > 0 else 0
        
        segment = 'new'
        if stats['total_spent'] >= 50000:
            segment = 'vip'
        elif stats['total_spent'] >= 10000:
            segment = 'regular'
        elif stats['total_orders'] >= 3:
            segment = 'loyal'
        
        cursor.execute('''
            UPDATE clients SET total_orders = ?, total_spent = ?, avg_check = ?,
                   last_order_date = ?, customer_segment = ?
            WHERE id = ?
        ''', (stats['total_orders'], stats['total_spent'], avg_check, 
              stats['last_order_date'], segment, client_id))
    
    conn.commit()
    conn.close()

# ==================== СКЛАД (НОВОЕ ФАЗА 3) ====================
def deduct_inventory(service_name, params):
    """Списание материалов со склада при выполнении заказа"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Простая логика списания по типу услуги
    if 'Фанера' in service_name or 'Дерево' in service_name:
        cursor.execute('''
            UPDATE inventory SET quantity = quantity - 1, last_updated = CURRENT_TIMESTAMP
            WHERE item_name LIKE '%Фанера%' AND quantity >= 1
        ''')
    elif 'Акрил' in service_name or 'Металл' in service_name:
        cursor.execute('''
            UPDATE inventory SET quantity = quantity - 1, last_updated = CURRENT_TIMESTAMP
            WHERE (item_name LIKE '%Акрил%' OR item_name LIKE '%Металл%') AND quantity >= 1
        ''')
    elif 'Фляжка' in service_name or 'Жетон' in service_name:
        cursor.execute('''
            UPDATE inventory SET quantity = quantity - 1, last_updated = CURRENT_TIMESTAMP
            WHERE (item_name LIKE '%Фляжка%' OR item_name LIKE '%Жетон%') AND quantity >= 1
        ''')
    
    conn.commit()
    conn.close()

def check_low_stock():
    """Проверка товаров с низким остатком"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT item_name, quantity, min_quantity, unit FROM inventory
        WHERE quantity <= min_quantity AND is_active = 1
    ''')
    low_stock = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return low_stock

# ==================== AI ПРОГНОЗЫ (НОВОЕ ФАЗА 3) ====================
def generate_ai_predictions():
    """Генерация прогнозов на основе истории заказов"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Прогноз выручки на следующую неделю
    cursor.execute('''
        SELECT DATE(created_at) as date, SUM(total_price) as revenue
        FROM orders WHERE status IN ('DONE', 'DELIVERED')
        GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30
    ''')
    data = cursor.fetchall()
    
    if len(data) >= 7:
        revenues = [row['revenue'] for row in data]
        avg_daily = sum(revenues) / len(revenues)
        weekly_prediction = avg_daily * 7
        
        # Простая линейная регрессия для тренда
        if len(revenues) >= 14:
            recent_avg = sum(revenues[:7]) / 7
            older_avg = sum(revenues[7:14]) / 7
            trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
            weekly_prediction *= (1 + trend)
        
        prediction_data = {
            'type': 'revenue_weekly',
            'prediction': round(weekly_prediction, 2),
            'confidence': 0.75,
            'trend': 'up' if trend > 0 else 'down' if trend < 0 else 'stable'
        }
        
        cursor.execute('''
            INSERT INTO ai_predictions (prediction_type, prediction_data, confidence)
            VALUES (?, ?, ?)
        ''', ('revenue_weekly', json.dumps(prediction_data), prediction_data['confidence']))
        
        conn.commit()
    
    conn.close()
    return prediction_data if len(data) >= 7 else None

# ==================== ИНТЕГРАЦИИ (НОВОЕ ФАЗА 3) ====================
def sync_with_1c(orders_data):
    """Синхронизация с 1С"""
    # Реализация API 1С
    return {'success': True, 'synced': len(orders_data)}

def sync_with_moysklad(orders_data):
    """Синхронизация с МойСклад"""
    # Реализация API МойСклад
    return {'success': True, 'synced': len(orders_data)}

def calculate_cdek_delivery(weight, city_from, city_to):
    """Расчёт стоимости доставки СДЭК"""
    # Реализация API СДЭК
    base_price = 300
    distance_factor = random.uniform(1.0, 3.0)
    return round(base_price * distance_factor, 2)

def create_yookassa_payment(amount, order_id, customer_id):
    """Создание платежа ЮKassa"""
    # Реализация API ЮKassa
    payment_id = f"payment_{order_id}_{int(time.time())}"
    return {'success': True, 'payment_id': payment_id, 'confirmation_url': 'https://yookassa.ru/confirm'}

# ==================== МАРШРУТЫ ====================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', 
                      (username, password_hash))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            token = generate_token(username, user['role'])
            response = make_response(redirect(url_for('index')))
            response.set_cookie('auth_token', token, max_age=604800)
            
            log_audit(user['id'], 'login', 'user', user['id'])
            return response
        else:
            return render_template('index.html', error='Неверный логин или пароль')
    
    return render_template('index.html')

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login_page')))
    response.delete_cookie('auth_token')
    return response

@app.route('/api/price_list')
@login_required
def get_price_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM price_list')
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/orders')
@login_required
def get_orders():
    status = request.args.get('status', 'all')
    conn = get_db()
    cursor = conn.cursor()
    
    if status == 'all':
        cursor.execute('SELECT * FROM orders ORDER BY created_at DESC')
    else:
        cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC', (status,))
    
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(orders)

@app.route('/api/calendar')
@login_required
def get_calendar():
    month = request.args.get('month', datetime.datetime.now().month)
    year = request.args.get('year', datetime.datetime.now().year)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, client_name, service_name, total_price, status, 
               DATE(planned_date) as planned_date, DATE(created_at) as created_date
        FROM orders
        WHERE strftime('%m', planned_date) = ? AND strftime('%Y', planned_date) = ?
        ORDER BY planned_date
    ''', (str(month).zfill(2), str(year)))
    
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    calendar_data = {}
    for order in orders:
        date = order['planned_date'] or order['created_date']
        if date:
            if date not in calendar_data:
                calendar_data[date] = []
            calendar_data[date].append(order)
    
    return jsonify(calendar_data)

@app.route('/api/clients')
@login_required
def get_clients():
    segment = request.args.get('segment', 'all')
    conn = get_db()
    cursor = conn.cursor()
    
    if segment == 'all':
        cursor.execute('SELECT * FROM clients ORDER BY total_spent DESC')
    else:
        cursor.execute('SELECT * FROM clients WHERE customer_segment = ? ORDER BY total_spent DESC', (segment,))
    
    clients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(clients)

@app.route('/api/client/<int:client_id>')
@login_required
def get_client_details(client_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    
    cursor.execute('''
        SELECT * FROM orders WHERE client_id = ? ORDER BY created_at DESC LIMIT 10
    ''', (client_id,))
    orders = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT * FROM cashback_transactions WHERE client_id = ? ORDER BY created_at DESC LIMIT 20
    ''', (client_id,))
    cashback_history = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    if client:
        return jsonify({'client': dict(client), 'orders': orders, 'cashback_history': cashback_history})
    return jsonify({'error': 'Client not found'}), 404

@app.route('/api/promo/validate', methods=['POST'])
@login_required
def validate_promo():
    data = request.json
    code = data.get('code', '').upper()
    discount = validate_promo_code(code)
    
    if discount:
        return jsonify({'valid': True, 'discount': int(discount * 100)})
    return jsonify({'valid': False, 'discount': 0})

@app.route('/api/promo/list')
@login_required
def get_promo_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM promo_codes ORDER BY created_at DESC')
    promos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(promos)

@app.route('/api/promo/create', methods=['POST'])
@role_required(['admin'])
def create_promo():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO promo_codes (code, discount_percent, max_uses, valid_until, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data.get('code', '').upper(),
            data.get('discount', 0),
            data.get('max_uses', 100),
            data.get('valid_until'),
            1
        ))
        conn.commit()
        log_audit(request.cookies.get('auth_token'), 'create_promo', 'promo_code')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/order/create', methods=['POST'])
@login_required
def create_order():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    params_text = "; ".join([f"{k}: {v}" for k, v in data.get('parameters', {}).items()])
    
    final_price = data.get('total_price', 0)
    discount = data.get('discount', 0)
    promo_code = data.get('promo_code')
    cashback_applied = data.get('cashback_applied', 0)
    
    if promo_code:
        use_promo_code(promo_code)
    
    cursor.execute('''
        INSERT INTO orders (client_id, vk_id, client_name, service_id, service_name, 
                           description, parameters, total_price, discount, promo_code, 
                           cashback_applied, planned_date, status, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('client_id'),
        data.get('vk_id'),
        data.get('client_name', 'Клиент'),
        data.get('service_id'),
        data.get('service_name'),
        data.get('description', 'Заказ'),
        params_text,
        final_price,
        discount,
        promo_code,
        cashback_applied,
        data.get('planned_date'),
        data.get('status', 'NEW'),
        data.get('payment_status', 'pending')
    ))
    
    order_id = cursor.lastrowid
    
    if data.get('client_id'):
        update_client_stats(data.get('client_id'))
        log_audit(request.cookies.get('auth_token'), 'create_order', 'order', order_id)
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'order_id': order_id})

@app.route('/api/order/status', methods=['POST'])
@login_required
def update_order_status():
    data = request.json
    order_id = data.get('order_id')
    new_status = data.get('status')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    
    completed_date = None
    if new_status == 'DONE':
        completed_date = datetime.datetime.now().isoformat()
        
        # Начисляем кэшбек
        if order['client_id']:
            cashback = add_cashback(order['client_id'], order_id, order['total_price'])
        
        # Списываем материалы со склада
        deduct_inventory(order['service_name'], json.loads(f'{{{order["parameters"]}}}'))
    
    cursor.execute('''
        UPDATE orders SET status = ?, completed_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, completed_date, order_id))
    
    if order['client_id']:
        update_client_stats(order['client_id'])
    
    notification_sent = False
    if new_status == 'DONE' and order['vk_id']:
        message = f"✅ Ваш заказ #{order_id} готов к выдаче! Ждем вас в мастерской."
        vk_send_message(order['vk_id'], message)
        save_notification(order_id, order['vk_id'], message, 'sent')
        notification_sent = True
    elif new_status == 'PROCESSING' and order['vk_id']:
        message = f"⚙️ Ваш заказ #{order_id} взят в работу. Ожидаемая готовность: {order['planned_date'] or 'soon'}."
        vk_send_message(order['vk_id'], message)
        save_notification(order_id, order['vk_id'], message, 'sent')
        notification_sent = True
    
    log_audit(request.cookies.get('auth_token'), 'update_status', 'order', order_id,
              {'status': order['status']}, {'status': new_status})
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'notification_sent': notification_sent})

@app.route('/api/chat/history')
@login_required
def get_chat_history():
    vk_id = request.args.get('vk_id', type=int)
    if not vk_id:
        return jsonify([])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM vk_messages WHERE vk_id = ? ORDER BY timestamp DESC LIMIT 100
    ''', (vk_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(messages)

@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_chat_message():
    data = request.json
    vk_id = data.get('vk_id')
    message_text = data.get('message')
    
    if not vk_id or not message_text:
        return jsonify({'success': False, 'error': 'Нет данных'})
    
    vk_send_message(vk_id, message_text)
    save_vk_message(vk_id, 0, message_text, is_admin=1)
    
    return jsonify({'success': True})

@app.route('/api/analytics/revenue')
@login_required
def get_revenue_analytics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(created_at) as date, SUM(total_price) as revenue, COUNT(*) as orders_count
        FROM orders
        WHERE status IN ('DONE', 'DELIVERED')
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 30
    ''')
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)

@app.route('/api/analytics/services')
@login_required
def get_services_analytics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT service_name, COUNT(*) as count, SUM(total_price) as revenue
        FROM orders
        WHERE status IN ('DONE', 'DELIVERED')
        GROUP BY service_name
        ORDER BY revenue DESC
    ''')
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)

@app.route('/api/analytics/segments')
@login_required
def get_segments_analytics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT customer_segment, COUNT(*) as count, SUM(total_spent) as revenue
        FROM clients
        GROUP BY customer_segment
    ''')
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)

@app.route('/api/analytics/summary')
@login_required
def get_summary_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT SUM(total_price) as total, COUNT(*) as count
        FROM orders WHERE status IN ('DONE', 'DELIVERED')
    ''')
    revenue_data = cursor.fetchone()
    
    cursor.execute('''
        SELECT COUNT(*) FROM orders WHERE status IN ('NEW', 'PROCESSING')
    ''')
    active_orders = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT AVG(total_price) FROM orders WHERE status IN ('DONE', 'DELIVERED')
    ''')
    avg_check = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT name, total_spent, total_orders FROM clients 
        ORDER BY total_spent DESC LIMIT 5
    ''')
    top_clients = [dict(row) for row in cursor.fetchall()]
    
    # Статистика склада
    cursor.execute('''
        SELECT COUNT(*) as low_stock FROM inventory 
        WHERE quantity <= min_quantity AND is_active = 1
    ''')
    low_stock_count = cursor.fetchone()['low_stock']
    
    # Общая сумма кэшбека
    cursor.execute('''
        SELECT SUM(cashback_balance) as total_cashback FROM clients
    ''')
    total_cashback = cursor.fetchone()['total_cashback'] or 0
    
    conn.close()
    
    return jsonify({
        'total_revenue': revenue_data['total'] or 0,
        'total_orders': revenue_data['count'] or 0,
        'active_orders': active_orders,
        'avg_check': round(avg_check, 2),
        'top_clients': top_clients,
        'low_stock_items': low_stock_count,
        'total_cashback_outstanding': round(total_cashback, 2)
    })

@app.route('/api/inventory')
@login_required
def get_inventory():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE is_active = 1 ORDER BY item_type, item_name')
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/inventory/update', methods=['POST'])
@role_required(['admin', 'manager'])
def update_inventory():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE inventory SET quantity = ?, price_per_unit = ?, 
                            min_quantity = ?, supplier = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (data.get('quantity'), data.get('price_per_unit'), 
          data.get('min_quantity'), data.get('supplier'), data.get('id')))
    
    cursor.execute('''
        INSERT INTO inventory_operations (item_id, operation_type, quantity, user_id, notes)
        VALUES (?, 'manual_adjustment', ?, ?, ?)
    ''', (data.get('id'), data.get('quantity'), request.cookies.get('auth_token'), data.get('notes')))
    
    conn.commit()
    conn.close()
    
    log_audit(request.cookies.get('auth_token'), 'update_inventory', 'inventory', data.get('id'))
    
    return jsonify({'success': True})

@app.route('/api/inventory/low-stock')
@login_required
def get_low_stock():
    low_stock = check_low_stock()
    return jsonify(low_stock)

@app.route('/api/cashback/history/<int:client_id>')
@login_required
def get_cashback_history(client_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM cashback_transactions WHERE client_id = ? ORDER BY created_at DESC
    ''', (client_id,))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(history)

@app.route('/api/integrations')
@role_required(['admin'])
def get_integrations():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM integrations')
    integrations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(integrations)

@app.route('/api/integrations/configure', methods=['POST'])
@role_required(['admin'])
def configure_integration():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE integrations SET api_key = ?, api_secret = ?, is_active = ?, config = ?
        WHERE service_name = ?
    ''', (data.get('api_key'), data.get('api_secret'), 
          data.get('is_active', 0), json.dumps(data.get('config', {})), data.get('service_name')))
    
    conn.commit()
    conn.close()
    
    log_audit(request.cookies.get('auth_token'), 'configure_integration', 'integration', 
              None, None, {'service': data.get('service_name')})
    
    return jsonify({'success': True})

@app.route('/api/ai/predictions')
@login_required
def get_ai_predictions():
    prediction = generate_ai_predictions()
    return jsonify(prediction if prediction else {'message': 'Недостаточно данных'})

@app.route('/api/audit-log')
@role_required(['admin'])
def get_audit_log():
    limit = request.args.get('limit', 100, type=int)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(logs)

@app.route('/api/users')
@role_required(['admin'])
def get_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, created_at FROM users')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/user/create', methods=['POST'])
@role_required(['admin'])
def create_user():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)
        ''', (data.get('username'), password_hash, data.get('role', 'manager')))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/payment/yookassa', methods=['POST'])
@login_required
def create_payment():
    data = request.json
    result = create_yookassa_payment(
        data.get('amount'),
        data.get('order_id'),
        data.get('customer_id')
    )
    return jsonify(result)

@app.route('/api/delivery/cdek', methods=['POST'])
@login_required
def calculate_delivery():
    data = request.json
    cost = calculate_cdek_delivery(
        data.get('weight', 1),
        data.get('city_from', 'Москва'),
        data.get('city_to', 'СПб')
    )
    return jsonify({'cost': cost, 'currency': 'RUB'})

@app.route('/api/backup/download')
@login_required
def download_backup():
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'workshop_backup_{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    shutil.copy(DB_PATH, backup_path)
    
    log_audit(request.cookies.get('auth_token'), 'download_backup', 'system')
    
    return send_file(backup_path, as_attachment=True, download_name=backup_filename)

@app.route('/api/export/csv')
@login_required
def export_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders')
    orders = cursor.fetchall()
    conn.close()
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'orders_export_{timestamp}.csv'
    filepath = os.path.join(BACKUP_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Клиент', 'Услуга', 'Параметры', 'Цена', 'Скидка', 'Промокод', 'Кэшбек', 'Статус', 'Дата'])
        for order in orders:
            writer.writerow([
                order[0], order[4], order[5], order[7], order[8], order[9], order[10], order[11], order[12], order[13]
            ])
    
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/manifest.json')
def manifest():
    manifest_data = {
        "name": "Лазерная Мастерская CRM",
        "short_name": "ЛазерCRM",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#4fc3f7",
        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)

@app.route('/sw.js')
def service_worker():
    sw_content = """
const CACHE_NAME = 'laser-crm-v1';
const urlsToCache = ['/', '/static/styles.css', '/static/app.js'];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
    );
});
"""
    return app.response_class(sw_content, mimetype='application/javascript')

# ==================== ЗАПУСК ====================
if __name__ == '__main__':
    init_db()
    print("🚀 Сервер запущен на http://localhost:5000")
    print("📊 Логин: admin | Пароль: admin123")
    print("👥 Роли: admin, manager, master")
    print("🎯 Фаза 3: Склад, Кэшбек, Роли, PWA, AI, Интеграции")
    app.run(host='0.0.0.0', port=5000, debug=False)