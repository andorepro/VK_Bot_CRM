# -*- coding: utf-8 -*-
"""
Лазерная Мастерская CRM - Клиент для ПК и мобильных устройств
Подключается к серверу на Raspberry Pi в локальной сети

Особенности:
- Оптимизированный интерфейс для ПК и телефонов (PWA)
- Работа через API сервера RPi
- Локальное кэширование для офлайн-режима
- Автоматическая синхронизация с сервером
- Поддержка темной/светлой темы
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
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, session
from functools import wraps
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from contextlib import contextmanager

# ==================== ЗАГРУЗКА КОНФИГУРАЦИИ ====================
from config import config

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates',
            static_url_path='/static')
app.secret_key = config.SECRET_KEY
app.debug = config.DEBUG_MODE
app.config['JSON_AS_ASCII'] = False

# Глобальные переменные
BASE_DIR = config.BASE_DIR
DB_PATH = config.DB_PATH
BACKUP_DIR = config.DB_BACKUP_DIR
SECRET_KEY = config.SECRET_KEY
SERVER_URL = config.get_server_url()

# Параметры клиента
MAX_CONNECTIONS = config.MAX_CONNECTIONS
CACHE_TTL = config.CACHE_TTL
THREAD_POOL_SIZE = config.THREAD_POOL_SIZE
OFFLINE_MODE = config.OFFLINE_MODE
AUTO_SYNC = config.AUTO_SYNC
SYNC_INTERVAL = config.SYNC_INTERVAL

# ==================== ЛОКАЛЬНЫЙ ПУЛ СОЕДИНЕНИЙ (КЭШ) ====================
class LocalConnectionPool:
    def __init__(self, db_path, max_connections=3):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = Lock()
        self._precreate_connections()
    
    def _create_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute(f'PRAGMA cache_size=-{config.CACHE_SIZE // 1024}')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _precreate_connections(self):
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

local_db_pool = LocalConnectionPool(DB_PATH, MAX_CONNECTIONS)

# ==================== КЭШИРОВАНИЕ ====================
class LRUCache:
    def __init__(self, max_size=50, ttl=60):
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

data_cache = LRUCache(max_size=50, ttl=CACHE_TTL)

# ==================== THREAD POOL ====================
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

def init_local_db():
    """Инициализация локальной БД для кэширования"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with local_db_pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица кэша заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_orders (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица кэша клиентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_clients (
                id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица офлайн-операций (для последующей синхронизации)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offline_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                data TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("✅ Локальная БД инициализирована")

# ==================== РАБОТА С СЕРВЕРОМ ====================
def make_server_request(endpoint, method='GET', data=None):
    """Отправка запроса к серверу RPi"""
    url = f"{SERVER_URL}{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, json=data, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'Server error: {response.status_code}'}
    
    except requests.exceptions.ConnectionError:
        return {'error': 'Server unavailable', 'offline': True}
    except requests.exceptions.Timeout:
        return {'error': 'Server timeout', 'offline': True}
    except Exception as e:
        return {'error': str(e), 'offline': True}

def sync_with_server():
    """Фоновая синхронизация с сервером"""
    if OFFLINE_MODE or not AUTO_SYNC:
        return
    
    while True:
        try:
            time.sleep(SYNC_INTERVAL)
            
            # Проверка доступности сервера
            result = make_server_request('/api/ping')
            if 'error' not in result:
                # Синхронизация офлайн-операций
                with local_db_pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM offline_operations WHERE synced = 0')
                    operations = cursor.fetchall()
                    
                    for op in operations:
                        # Отправка операции на сервер
                        op_data = json.loads(op['data'])
                        make_server_request(f"/api/sync/{op['operation_type']}", method='POST', data=op_data)
                        
                        # Пометка как синхронизированное
                        cursor.execute('UPDATE offline_operations SET synced = 1 WHERE id = ?', (op['id'],))
                    
                    conn.commit()
                    
        except Exception as e:
            print(f"Sync error: {e}")

# Запуск фоновой синхронизации
if AUTO_SYNC and not OFFLINE_MODE:
    sync_thread = Thread(target=sync_with_server, daemon=True)
    sync_thread.start()

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

# ==================== МАРШРУТЫ ====================
@app.route('/')
def index():
    """Главная страница - оптимизирована для ПК и мобильных"""
    return render_template('index.html', server_url=SERVER_URL)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Авторизация через сервер RPi"""
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Запрос к серверу авторизации
        result = make_server_request('/api/login', method='POST', 
                                     data={'username': username, 'password': password})
        
        if 'token' in result:
            resp = make_response(jsonify({'success': True}))
            resp.set_cookie('token', result['token'], max_age=60*60*24*7)
            return resp
        
        return jsonify({'error': result.get('error', 'Ошибка авторизации')}), 401
    
    return render_template('login.html')

@app.route('/api/orders')
@token_required
def get_orders(current_user):
    """Получение списка заказов с сервера"""
    # Проверка кэша
    cached = data_cache.get('orders')
    if cached:
        return jsonify(cached)
    
    # Запрос к серверу
    result = make_server_request('/api/orders')
    
    if 'error' not in result:
        data_cache.set('orders', result)
        return jsonify(result)
    
    return jsonify(result), 500

@app.route('/api/clients')
@token_required
def get_clients(current_user):
    """Получение списка клиентов"""
    cached = data_cache.get('clients')
    if cached:
        return jsonify(cached)
    
    result = make_server_request('/api/clients')
    
    if 'error' not in result:
        data_cache.set('clients', result)
        return jsonify(result)
    
    return jsonify(result), 500

@app.route('/api/dashboard')
@token_required
def get_dashboard(current_user):
    """Получение данных дашборда"""
    result = make_server_request('/api/dashboard')
    return jsonify(result)

@app.route('/api/calculate', methods=['POST'])
@token_required
def calculate(current_user):
    """Расчёт стоимости заказа через сервер"""
    data = request.json
    result = make_server_request('/api/calculate', method='POST', data=data)
    return jsonify(result)

@app.route('/api/create_order', methods=['POST'])
@token_required
def create_order(current_user):
    """Создание заказа"""
    data = request.json
    
    if OFFLINE_MODE:
        # Сохранение в офлайн-очередь
        with local_db_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO offline_operations (operation_type, data)
                VALUES (?, ?)
            ''', ('create_order', json.dumps(data)))
            conn.commit()
        return jsonify({'success': True, 'offline': True, 'message': 'Заказ сохранён для синхронизации'})
    
    result = make_server_request('/api/create_order', method='POST', data=data)
    return jsonify(result)

@app.route('/api/ping')
def ping():
    """Проверка доступности"""
    return jsonify({'status': 'ok', 'server': SERVER_URL})

@app.route('/manifest.json')
def manifest():
    """PWA манифест"""
    return jsonify({
        "name": "Лазерная Мастерская CRM",
        "short_name": "CRM Laser",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#4fc3f7",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.route('/service-worker.js')
def service_worker():
    """Service Worker для PWA"""
    sw_content = """
const CACHE_NAME = 'laser-crm-client-v1';
const urlsToCache = ['/', '/static/styles.css', '/static/app.js'];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            if (response) return response;
            return fetch(event.request);
        })
    );
});
"""
    return app.response_class(sw_content, mimetype='application/javascript')

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Laser Workshop Application Starting...")
    print(f"🔒 HTTPS: {'Enabled' if config.USE_HTTPS else 'Disabled'}")
    print(f"🌐 Host: {config.HOST}")
    print(f"🔌 Port: {config.PORT}")
    print("=" * 50)
    
    if config.USE_HTTPS:
        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=config.CERT_FILE, keyfile=config.KEY_FILE)
        app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True, ssl_context=context)
    else:
        app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
