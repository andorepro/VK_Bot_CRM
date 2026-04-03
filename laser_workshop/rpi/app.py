# -*- coding: utf-8 -*-
"""
Лазерная Мастерская CRM - Оптимизированная версия для Raspberry Pi 3 Model B+
Отличия от основной версии:
- Уменьшенные параметры пула соединений и кэша
- Отключены AI прогнозы по умолчанию
- Оптимизированные настройки SQLite для ARM
"""

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

# ==================== ЗАГРУЗКА КОНФИГУРАЦИИ ====================
from config import config

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__, 
            static_folder=config.BASE_DIR + '/../static' if hasattr(config, 'BASE_DIR') else os.path.join(os.path.dirname(os.path.abspath(__file__)), '../static'), 
            template_folder=config.BASE_DIR + '/../templates' if hasattr(config, 'BASE_DIR') else os.path.join(os.path.dirname(os.path.abspath(__file__)), '../templates'),
            static_url_path='/static')
app.secret_key = config.SECRET_KEY
app.debug = config.DEBUG_MODE
app.config['JSON_AS_ASCII'] = False

# Глобальные переменные из конфигурации
BASE_DIR = config.BASE_DIR
DB_PATH = config.DB_PATH
BACKUP_DIR = config.DB_BACKUP_DIR
SECRET_KEY = config.SECRET_KEY
VK_TOKEN = config.VK_TOKEN
VK_GROUP_ID = config.VK_GROUP_ID

# Оптимизация для RPi из конфигурации
MAX_CONNECTIONS = config.MAX_CONNECTIONS
CACHE_TTL = config.CACHE_TTL
MAX_USER_STATES = config.MAX_USER_STATES
THREAD_POOL_SIZE = config.THREAD_POOL_SIZE
AI_PROGNOSIS_ENABLED = config.AI_PROGNOSIS

# ==================== ОПТИМИЗИРОВАННЫЙ ПУЛ СОЕДИНЕНИЙ ====================
class ConnectionPool:
    def __init__(self, db_path, max_connections=5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = Lock()
        self._initialized = False
        # Предварительное создание всех соединений для быстрого старта
        self._precreate_connections()
    
    def _create_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # Максимальная оптимизация для RPi
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-32000')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA mmap_size=268435456')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _precreate_connections(self):
        """Предварительное создание пула соединений"""
        for _ in range(self.max_connections):
            try:
                conn = self._create_connection()
                self._pool.append(conn)
            except Exception as e:
                print(f"⚠️ Warning: Could not pre-create connection: {e}")
    
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
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'manager',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица клиентов
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
        
        # Таблица склада
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
        
        # Таблица операций склада
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
        
        # Таблица кэшбек-транзакций
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
        
        # Таблица интеграций
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
        
        # Таблица AI прогнозов (отключена для RPi по умолчанию)
        if AI_PROGNOSIS_ENABLED:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_type TEXT NOT NULL,
                    prediction_data TEXT NOT NULL,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Таблица аудита
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

# Инициализация пула соединений
db_pool = ConnectionPool(DB_PATH, MAX_CONNECTIONS)

# ==================== КЭШИРОВАНИЕ (уменьшенное для RPi) ====================
class LRUCache:
    def __init__(self, max_size=50, ttl=180):  # Уменьшено с 100/300
        self.cache = OrderedDict()
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl
        self.lock = Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
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

price_cache = LRUCache(max_size=10, ttl=CACHE_TTL)
client_cache = LRUCache(max_size=200, ttl=CACHE_TTL)  # Уменьшено с 500
promo_cache = LRUCache(max_size=50, ttl=60)

# ==================== THREAD POOL (уменьшен для RPi) ====================
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

def run_async(func, *args, **kwargs):
    return executor.submit(func, *args, **kwargs)

def get_db():
    """Устаревшая функция, используется pool"""
    return db_pool.get_connection().__enter__()

def init_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        db_pool.init_db_schema(cursor)
        conn.commit()
        
        # Создание пользователя admin по умолчанию
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, role) 
                VALUES (?, ?, 'admin')
            ''', ('admin', password_hash))
            conn.commit()
            print("✅ Создан пользователь admin / admin123")

# ==================== ДЕКОРАТОРЫ ====================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({'error': 'Токен не найден'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = data['username']
        except:
            return jsonify({'error': 'Неверный токен'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated(current_user, *args, **kwargs):
            with db_pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role FROM users WHERE username = ?', (current_user,))
                user = cursor.fetchone()
                if not user or user['role'] not in required_role:
                    return jsonify({'error': 'Недостаточно прав'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator

# ==================== МАРШРУТЫ ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', 
                      (username, password_hash))
        user = cursor.fetchone()
        
        if user:
            token = jwt.encode({
                'username': username,
                'role': user['role'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
            }, SECRET_KEY, algorithm='HS256')
            
            resp = make_response(jsonify({'success': True, 'role': user['role']}))
            resp.set_cookie('token', token, max_age=86400)
            return resp
    
    return jsonify({'success': False, 'error': 'Неверные учётные данные'}), 401

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('index')))
    resp.delete_cookie('token')
    return resp

@app.route('/api/users/current')
@token_required
def get_current_user(current_user):
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, role FROM users WHERE username = ?', (current_user,))
        user = cursor.fetchone()
    return jsonify(dict(user)) if user else jsonify({'error': 'Пользователь не найден'}), 404

# Остальные API endpoints можно добавить по необходимости
# Для RPi версии рекомендуется включать только необходимые функции

if __name__ == '__main__':
    print("🔬 Лазерная Мастерская CRM (RPi Optimized)")
    print(f"📊 MAX_CONNECTIONS: {config.MAX_CONNECTIONS}")
    print(f"⚡ THREAD_POOL_SIZE: {config.THREAD_POOL_SIZE}")
    print(f"💾 CACHE_TTL: {config.CACHE_TTL}s")
    print(f"🤖 AI_PROGNOSIS: {'Enabled' if config.AI_PROGNOSIS else 'Disabled'}")
    print(f"🔒 HTTPS: {'Enabled' if config.USE_HTTPS else 'Disabled'}")
    print("=" * 50)
    
    init_db()
    
    # Запуск на всех интерфейсах для доступа из сети
    if config.USE_HTTPS:
        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=config.CERT_FILE, keyfile=config.KEY_FILE)
        app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True, ssl_context=context)
    else:
        app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
