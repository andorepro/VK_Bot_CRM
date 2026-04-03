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

# ==================== КОНФИГУРАЦИЯ ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'workshop.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
SECRET_KEY = 'laser_workshop_secret_key_2026_change_this'
VK_TOKEN = 'YOUR_VK_TOKEN_HERE'
VK_GROUP_ID = 'YOUR_GROUP_ID'

# ==================== ИНИЦИАЛИЗАЦИЯ FLASK ====================
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ==================== БАЗА ДАННЫХ ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица клиентов (обновлённая для LTV)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица прайс-листа (11 типов)
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
    
    # Таблица заказов (обновлённая с датами)
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
            status TEXT DEFAULT 'NEW',
            planned_date TIMESTAMP,
            completed_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (service_id) REFERENCES price_list(id)
        )
    ''')
    
    # Таблица промокодов (НОВОЕ для Фазы 2)
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
    
    # Таблица уведомлений (НОВОЕ для Фазы 2)
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
    
    # Создаем админа
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
    
    conn.commit()
    conn.close()

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

def apply_discount(total_price, quantity, promo_code=None):
    discount = 0
    discount_source = 'quantity'
    
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
    return round(discounted_price, 2), int(discount * 100), discount_source

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
        
        # Сегментация клиентов
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
    
    # Группировка по дням
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
    
    conn.close()
    
    if client:
        return jsonify({'client': dict(client), 'orders': orders})
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
@login_required
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
    
    # Применяем промокод если есть
    final_price = data.get('total_price', 0)
    discount = data.get('discount', 0)
    promo_code = data.get('promo_code')
    
    if promo_code:
        use_promo_code(promo_code)
    
    cursor.execute('''
        INSERT INTO orders (client_id, vk_id, client_name, service_id, service_name, 
                           description, parameters, total_price, discount, promo_code, 
                           planned_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get('planned_date'),
        data.get('status', 'NEW')
    ))
    
    order_id = cursor.lastrowid
    
    # Обновляем статистику клиента
    if data.get('client_id'):
        update_client_stats(data.get('client_id'))
    
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
    
    # Получаем данные заказа
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    
    # Обновляем статус
    completed_date = None
    if new_status == 'DONE':
        completed_date = datetime.datetime.now().isoformat()
    
    cursor.execute('''
        UPDATE orders SET status = ?, completed_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, completed_date, order_id))
    
    # Обновляем статистику клиента
    if order['client_id']:
        update_client_stats(order['client_id'])
    
    # Отправляем уведомления
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
    
    # Общая выручка
    cursor.execute('''
        SELECT SUM(total_price) as total, COUNT(*) as count
        FROM orders WHERE status IN ('DONE', 'DELIVERED')
    ''')
    revenue_data = cursor.fetchone()
    
    # Активные заказы
    cursor.execute('''
        SELECT COUNT(*) FROM orders WHERE status IN ('NEW', 'PROCESSING')
    ''')
    active_orders = cursor.fetchone()[0]
    
    # Средний чек
    cursor.execute('''
        SELECT AVG(total_price) FROM orders WHERE status IN ('DONE', 'DELIVERED')
    ''')
    avg_check = cursor.fetchone()[0] or 0
    
    # Топ клиентов
    cursor.execute('''
        SELECT name, total_spent, total_orders FROM clients 
        ORDER BY total_spent DESC LIMIT 5
    ''')
    top_clients = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'total_revenue': revenue_data['total'] or 0,
        'total_orders': revenue_data['count'] or 0,
        'active_orders': active_orders,
        'avg_check': round(avg_check, 2),
        'top_clients': top_clients
    })

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
    conn.close()
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'orders_export_{timestamp}.csv'
    filepath = os.path.join(BACKUP_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Клиент', 'Услуга', 'Параметры', 'Цена', 'Скидка', 'Промокод', 'Статус', 'Дата'])
        for order in orders:
            writer.writerow([
                order[0], order[4], order[5], order[7], order[8], order[9], order[10], order[11], order[12]
            ])
    
    return send_file(filepath, as_attachment=True, download_name=filename)

# ==================== ЗАПУСК ====================
if __name__ == '__main__':
    init_db()
    print("🚀 Сервер запущен на http://localhost:5000")
    print("📊 Логин: admin | Пароль: admin123")
    print("🎯 Фаза 2: Промокоды, Календарь, LTV, Аналитика")
    app.run(host='0.0.0.0', port=5000, debug=False)