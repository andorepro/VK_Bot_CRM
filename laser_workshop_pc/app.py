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
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, send_file
from functools import wraps
from threading import Thread
import time

# ==================== ЗАГРУЗКА КОНФИГУРАЦИИ ====================
from config import config

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.debug = config.DEBUG_MODE

# Глобальные переменные из конфигурации
BASE_DIR = config.BASE_DIR
DB_PATH = config.DB_PATH
BACKUP_DIR = config.DB_BACKUP_DIR
SECRET_KEY = config.SECRET_KEY
VK_TOKEN = config.VK_TOKEN
VK_GROUP_ID = config.VK_GROUP_ID

# Оптимизация для быстрого запуска на PC
MAX_CONNECTIONS = config.MAX_CONNECTIONS
THREAD_POOL_SIZE = config.THREAD_POOL_SIZE
CACHE_SIZE = config.CACHE_SIZE
AI_PROGNOSIS = config.AI_PROGNOSIS
DEBUG_MODE = config.DEBUG_MODE

# ==================== БАЗА ДАННЫХ (ОПТИМИЗИРОВАНО) ====================
# Пул соединений для быстрого доступа
_db_pool = []

def get_db():
    """Получение соединения из пула или создание нового"""
    if _db_pool:
        conn = _db_pool.pop()
    else:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-65536')
        conn.execute('PRAGMA busy_timeout=30000')
        conn.row_factory = sqlite3.Row
    return conn

def return_db(conn):
    """Возврат соединения в пул"""
    if len(_db_pool) < MAX_CONNECTIONS:
        _db_pool.append(conn)
    else:
        return_db(conn)

def _precreate_connections():
    """Предварительное создание пула соединений при старте"""
    for _ in range(MAX_CONNECTIONS):
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-65536')
        conn.execute('PRAGMA busy_timeout=30000')
        conn.row_factory = sqlite3.Row
        _db_pool.append(conn)

def init_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей (админы)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица прайс-листа (11 типов расчетов)
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
            status TEXT DEFAULT 'NEW',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (service_id) REFERENCES price_list(id)
        )
    ''')
    
    # Таблица сообщений VK (для чата в CRM)
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
    
    # Создаем админа по умолчанию (admin / admin123)
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                      ('admin', password_hash))
    
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
    
    # autocommit
    return_db(conn)

# ==================== JWT АВТОРИЗАЦИЯ ====================
def generate_token(username):
    payload = {
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['username']
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
        username = verify_token(token)
        if not username:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ==================== VK API ФУНКЦИИ ====================
def vk_send_message(vk_id, message):
    """Отправка сообщения ВКонтакте"""
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

def vk_get_messages(vk_id, count=100):
    """Получение истории сообщений"""
    try:
        url = 'https://api.vk.com/method/messages.getHistory'
        params = {
            'user_id': vk_id,
            'count': count,
            'access_token': VK_TOKEN,
            'v': '5.131'
        }
        response = requests.get(url, params=params, timeout=10)
        return response.json().get('response', {}).get('items', [])
    except Exception as e:
        print(f"VK Get Error: {e}")
        return []

def save_vk_message(vk_id, from_user, message_text, is_admin=0):
    """Сохранение сообщения в БД"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vk_messages (vk_id, from_user, message_text, is_admin)
        VALUES (?, ?, ?, ?)
    ''', (vk_id, from_user, message_text, is_admin))
    # autocommit
    return_db(conn)

# ==================== КАЛЬКУЛЯТОР (11 ТИПОВ) ====================
def calculate_price(calc_type, params, base_price):
    """Расчет стоимости по 11 типам"""
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

def apply_discount(total_price, quantity):
    """Применение оптовых скидок"""
    discount = 0
    if quantity >= 100:
        discount = 0.20
    elif quantity >= 50:
        discount = 0.15
    elif quantity >= 20:
        discount = 0.10
    elif quantity >= 10:
        discount = 0.05
    
    discounted_price = total_price * (1 - discount)
    return round(discounted_price, 2), int(discount * 100)

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
        return_db(conn)
        
        if user:
            token = generate_token(username)
            response = make_response(redirect(url_for('index')))
            response.set_cookie('auth_token', token, max_age=604800)
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
    return_db(conn)
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
    return_db(conn)
    return jsonify(orders)

@app.route('/api/clients')
@login_required
def get_clients():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients ORDER BY total_spent DESC')
    clients = [dict(row) for row in cursor.fetchall()]
    return_db(conn)
    return jsonify(clients)

@app.route('/api/order/create', methods=['POST'])
@login_required
def create_order():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Формируем плоское текстовое описание (без JSON)
    params_text = "; ".join([f"{k}: {v}" for k, v in data.get('parameters', {}).items()])
    
    cursor.execute('''
        INSERT INTO orders (client_id, vk_id, client_name, service_id, service_name, 
                           description, parameters, total_price, discount, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('client_id'),
        data.get('vk_id'),
        data.get('client_name', 'Клиент'),
        data.get('service_id'),
        data.get('service_name'),
        data.get('description', 'Заказ'),
        params_text,
        data.get('total_price', 0),
        data.get('discount', 0),
        data.get('status', 'NEW')
    ))
    
    order_id = cursor.lastrowid
    # autocommit
    return_db(conn)
    
    return jsonify({'success': True, 'order_id': order_id})

@app.route('/api/order/status', methods=['POST'])
@login_required
def update_order_status():
    data = request.json
    order_id = data.get('order_id')
    new_status = data.get('status')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, order_id))
    
    # Если статус DONE - отправляем уведомление в VK
    if new_status == 'DONE':
        cursor.execute('SELECT vk_id, client_name FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        if order and order[0]:
            message = f"✅ Ваш заказ #{order_id} готов к выдаче! Ждем вас в мастерской."
            vk_send_message(order[0], message)
    
    # autocommit
    return_db(conn)
    
    return jsonify({'success': True})

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
    return_db(conn)
    
    return jsonify(messages)

@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_chat_message():
    data = request.json
    vk_id = data.get('vk_id')
    message_text = data.get('message')
    
    if not vk_id or not message_text:
        return jsonify({'success': False, 'error': 'Нет данных'})
    
    # Отправляем в VK
    vk_send_message(vk_id, message_text)
    
    # Сохраняем в БД
    save_vk_message(vk_id, 0, message_text, is_admin=1)
    
    return jsonify({'success': True})

@app.route('/api/analytics/revenue')
@login_required
def get_revenue_analytics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(created_at) as date, SUM(total_price) as revenue
        FROM orders
        WHERE status IN ('DONE', 'DELIVERED')
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 30
    ''')
    data = [dict(row) for row in cursor.fetchall()]
    return_db(conn)
    return jsonify(data)

@app.route('/api/backup/download')
@login_required
def download_backup():
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'workshop_backup_{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    shutil.copy(DB_PATH, backup_path)
    
    return send_file(backup_path, as_attachment=True, download_name=backup_filename)

@app.route('/api/export/csv')
@login_required
def export_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders')
    orders = cursor.fetchall()
    return_db(conn)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'orders_export_{timestamp}.csv'
    filepath = os.path.join(BACKUP_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Клиент', 'Услуга', 'Параметры', 'Цена', 'Статус', 'Дата'])
        for order in orders:
            writer.writerow([
                order[0], order[4], order[5], order[7], order[8], order[9], order[10]
            ])
    
    return send_file(filepath, as_attachment=True, download_name=filename)

# ==================== ЗАПУСК (ОПТИМИЗИРОВАН) ====================
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