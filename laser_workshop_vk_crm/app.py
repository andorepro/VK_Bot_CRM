# sys.stdout.reconfigure(encoding='utf-8')
import sys
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import hashlib
import datetime
import threading
import json
import requests
import time
import platform
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_file, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv('DB_PATH', os.path.join(BASE_DIR, 'database.db'))
SECRET_KEY = os.getenv('SECRET_KEY', 'change_this_secret_key_in_production')
VK_TOKEN = os.getenv('VK_TOKEN', '')
VK_GROUP_ID = os.getenv('VK_GROUP_ID', '')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
ADMIN_PASSWORD_HASH = generate_password_hash(DEFAULT_ADMIN_PASSWORD)

# Server settings
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
USE_HTTPS = os.getenv('USE_HTTPS', 'True').lower() == 'true'

# Platform detection and optimization
PLATFORM = os.getenv('PLATFORM', 'auto')
if PLATFORM == 'auto':
    if platform.machine() in ['armv7l', 'armv6l', 'aarch64'] or 'raspberry' in platform.node().lower():
        PLATFORM = 'rpi'
    else:
        PLATFORM = 'pc'

# Resource limits based on platform
if PLATFORM == 'rpi':
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', 5))
    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', 2))
    CACHE_SIZE_MB = int(os.getenv('CACHE_SIZE_MB', 32))
    print("🍓 Running in Raspberry Pi mode (optimized for low resources)")
else:
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', 10))
    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', 5))
    CACHE_SIZE_MB = int(os.getenv('CACHE_SIZE_MB', 64))
    print("💻 Running in PC mode (full features enabled)")

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# --- DATABASE INITIALIZATION ---
def get_db():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # Autocommit for speed
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(f"PRAGMA cache_size=-{CACHE_SIZE_MB * 1024}")  # Set cache size in KB
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table (admins)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT
    )''')
    
    # Price list table (11 algorithms)
    c.execute('''CREATE TABLE IF NOT EXISTS price_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        calc_type TEXT UNIQUE,
        base_price REAL,
        description TEXT
    )''')
    
    # Clients table (from VK)
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        vk_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        total_orders INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0.0,
        last_seen INTEGER
    )''')
    
    # Orders table (Flat-text architecture in description)
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_vk_id INTEGER,
        status TEXT DEFAULT 'NEW',
        total_price REAL,
        description TEXT,
        created_at INTEGER,
        updated_at INTEGER,
        machine_type TEXT DEFAULT 'ANY',
        FOREIGN KEY(client_vk_id) REFERENCES clients(vk_id)
    )''')

    # Chat messages table
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vk_id INTEGER,
        message_text TEXT,
        is_from_admin INTEGER DEFAULT 0,
        timestamp INTEGER,
        FOREIGN KEY(vk_id) REFERENCES clients(vk_id)
    )''')

    # Populate price list if empty
    c.execute("SELECT count(*) FROM price_list")
    if c.fetchone()[0] == 0:
        services = [
            ("Фиксированная цена", "fixed", 500.0, "Фляжка, жетон, брелок - штучный товар"),
            ("Шильды/Дерево (см²)", "area_cm2", 15.0, "Гравировка по площади: (Длина/10 * Ширина/10) * Цена"),
            ("Резка фанеры (мм/м)", "meter_thickness", 12.0, "Ortur резка: Метры * (Цена * (Толщина/3.0))"),
            ("Гравировка MOPA (мин)", "per_minute", 25.0, "Долгая цветная гравировка: Минуты * Цена"),
            ("Кольца/Ручки (символ)", "per_char", 10.0, "Гравировка текста: Символы * Цена"),
            ("Векторная резка (м)", "vector_length", 40.0, "Промышленная контурная резка: Метры * Цена"),
            ("B2B Тираж (настройка+шт)", "setup_batch", 1000.0, "Настройка + (Цена_шт * Тираж) со скидками"),
            ("Фото (растр DPI)", "photo_raster", 20.0, "Фото на металле/дереве: Площадь * Цена * DPI_Множитель"),
            ("Термосы (Ось)", "cylindrical", 1.5, "Гравировка на цилиндре: (Диаметр * 3.14 * Длина/100) * Цена"),
            ("3D Клише (объем)", "volume_3d", 50.0, "Глубокая 3D гравировка: (Длина/10 * Ширина/10) * Глубина * Цена"),
            ("Материал + Резка", "material_and_cut", 10.0, "Комплекс: (Площадь*Цена_мат) + (Метры_реза*Цена_реза)")
        ]
        c.executemany("INSERT INTO price_list (name, calc_type, base_price, description) VALUES (?, ?, ?, ?)", services)
        print("✅ Price list initialized with 11 services")
        
    # Create default admin user
    c.execute("SELECT count(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', ADMIN_PASSWORD_HASH))
        print("✅ Default admin user created (login: admin, password: admin123)")
    
    conn.close()
    print("✅ Database initialized successfully")

# --- PRICE CALCULATION ENGINE (11 ALGORITHMS) ---
def calculate_price(calc_type, params):
    """
    Calculates price based on 11 different algorithms.
    params: dict with keys: length, width, thickness, minutes, chars, batch, diameter, depth, material_price, cut_price, qty, unit_price, dpi, cut_length
    """
    p = params
    price = 0.0
    
    try:
        if calc_type == 'fixed':
            # Штучный товар
            price = p.get('base_price', 0) * p.get('qty', 1)
            
        elif calc_type == 'area_cm2':
            # Шильды/Дерево: (Длина/10 * Ширина/10) * Цена
            area = (p.get('length', 0) / 10.0) * (p.get('width', 0) / 10.0)
            price = area * p.get('base_price', 0) * p.get('qty', 1)
            
        elif calc_type == 'meter_thickness':
            # Резка фанеры: Метры * (Цена * (Толщина/3.0))
            meters = p.get('length', 0) / 1000.0  # mm to meters
            factor = p.get('thickness', 3.0) / 3.0
            price = meters * (p.get('base_price', 0) * factor) * p.get('qty', 1)
            
        elif calc_type == 'per_minute':
            # MOPA 3D: Минуты * Цена
            price = p.get('minutes', 0) * p.get('base_price', 0)
            
        elif calc_type == 'per_char':
            # Кольца: Символы * Цена
            price = p.get('chars', 0) * p.get('base_price', 0) * p.get('qty', 1)
            
        elif calc_type == 'vector_length':
            # Пром. резка: Метры * Цена
            meters = p.get('length', 0) / 1000.0
            price = meters * p.get('base_price', 0)
            
        elif calc_type == 'setup_batch':
            # B2B тираж: Настройка + (Цена_шт * Тираж) со скидками
            setup = p.get('base_price', 0)  # Base price is setup cost
            unit_price = p.get('unit_price', 0)
            qty = p.get('qty', 1)
            
            # Volume discounts: 10pcs-5%, 20pcs-10%, 50pcs-15%, 100pcs-20%
            discount = 0
            if qty >= 100:
                discount = 0.20
            elif qty >= 50:
                discount = 0.15
            elif qty >= 20:
                discount = 0.10
            elif qty >= 10:
                discount = 0.05
            
            price = setup + (unit_price * qty * (1 - discount))
            
        elif calc_type == 'photo_raster':
            # Фото: Площадь * Цена * DPI_Множитель
            area = (p.get('length', 0) / 10.0) * (p.get('width', 0) / 10.0)
            dpi_mult = 1.5 if p.get('dpi', 300) > 600 else 1.0
            price = area * p.get('base_price', 0) * dpi_mult
            
        elif calc_type == 'cylindrical':
            # Термосы: (Диаметр * 3.14 * Длина/100) * Цена
            area = (p.get('diameter', 0) * 3.14 * p.get('length', 0)) / 100.0
            price = area * p.get('base_price', 0)
            
        elif calc_type == 'volume_3d':
            # 3D Клише: (Длина/10 * Ширина/10) * Глубина * Цена
            vol = (p.get('length', 0)/10.0) * (p.get('width', 0)/10.0) * p.get('depth', 0)
            price = vol * p.get('base_price', 0)
            
        elif calc_type == 'material_and_cut':
            # Мат+Рез: ((Длина/10 * Ширина/10) * Цена_материала) + (Метры_реза * Цена_реза)
            mat_area = (p.get('length', 0)/10.0) * (p.get('width', 0)/10.0)
            cut_len = p.get('cut_length', 0) / 1000.0
            price = (mat_area * p.get('material_price', 0)) + (cut_len * p.get('cut_price', 0))
            
    except Exception as e:
        print(f"❌ Error calculating price: {e}")
        return 0.0
        
    return round(price, 2)

def send_vk_message(user_id, message):
    """Send message via VK API"""
    if not VK_TOKEN or not VK_GROUP_ID:
        print(f"[MOCK VK] To {user_id}: {message}")
        return True
    
    try:
        from urllib.parse import quote
        url = f"https://api.vk.com/method/messages.send?peer_id={user_id}&message={quote(message)}&access_token={VK_TOKEN}&v=5.131&random_id={int(time.time())}"
        r = requests.get(url, timeout=5)
        result = r.json()
        if 'error' in result:
            print(f"VK Error: {result['error']}")
            return False
        return True
    except Exception as e:
        print(f"❌ VK Send Error: {e}")
        return False

# --- AUTH DECORATOR ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data['username']
        except:
            return jsonify({'error': 'Token invalid'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db()
    user = conn.execute("SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        token = jwt.encode({
            'username': username, 
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, algorithm="HS256")
        
        resp = make_response(jsonify({'success': True}))
        resp.set_cookie('auth_token', token, httponly=True, max_age=86400, secure=USE_HTTPS, samesite='Lax')
        return resp
    
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/orders', methods=['GET'])
@token_required
def get_orders(username):
    conn = get_db()
    orders = conn.execute('''
        SELECT o.*, c.first_name, c.last_name 
        FROM orders o 
        LEFT JOIN clients c ON o.client_vk_id = c.vk_id 
        ORDER BY o.created_at DESC
    ''').fetchall()
    conn.close()
    
    result = [dict(row) for row in orders]
    return jsonify(result)

@app.route('/api/orders/status', methods=['POST'])
@token_required
def update_order_status(username):
    data = request.json
    order_id = data.get('id')
    new_status = data.get('status')
    
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    
    if not order:
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
        
    # Update status
    conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", 
                 (new_status, int(time.time()), order_id))
    
    # If status is DONE, send notification to client
    if new_status == 'DONE' and order['client_vk_id']:
        msg = f"✅ Заказ #{order_id} готов! Можно забирать."
        send_vk_message(order['client_vk_id'], msg)
        print(f"📤 Sent completion notification to VK user {order['client_vk_id']}")
        
    conn.close()
    return jsonify({'success': True})

@app.route('/api/price_list', methods=['GET'])
@token_required
def get_price_list(username):
    conn = get_db()
    items = conn.execute("SELECT * FROM price_list").fetchall()
    conn.close()
    return jsonify([dict(i) for i in items])

@app.route('/api/calculate', methods=['POST'])
@token_required
def api_calculate(username):
    data = request.json
    price = calculate_price(data['calc_type'], data['params'])
    return jsonify({'price': price})

@app.route('/api/clients', methods=['GET'])
@token_required
def get_clients(username):
    conn = get_db()
    clients = conn.execute("SELECT * FROM clients ORDER BY total_spent DESC").fetchall()
    conn.close()
    return jsonify([dict(c) for c in clients])

@app.route('/api/chat/history', methods=['GET'])
@token_required
def get_chat_history(username):
    vk_id = request.args.get('vk_id')
    if not vk_id:
        return jsonify([])
    
    conn = get_db()
    messages = conn.execute(
        "SELECT * FROM chat_messages WHERE vk_id=? ORDER BY timestamp ASC LIMIT 100", 
        (vk_id,)
    ).fetchall()
    conn.close()
    
    return jsonify([dict(m) for m in messages])

@app.route('/api/chat/send', methods=['POST'])
@token_required
def send_chat_message(username):
    data = request.json
    user_id = data.get('user_id')
    text = data.get('text')
    
    if not user_id or not text:
        return jsonify({'error': 'Missing parameters'}), 400
    
    # Send to VK
    success = send_vk_message(user_id, text)
    
    if success:
        # Save to local DB
        conn = get_db()
        conn.execute(
            "INSERT INTO chat_messages (vk_id, message_text, is_from_admin, timestamp) VALUES (?, ?, 1, ?)",
            (user_id, text, int(time.time()))
        )
        conn.close()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Failed to send'}), 500

@app.route('/backup')
@token_required
def download_backup(username):
    if not os.path.exists(DB_PATH):
        return "Database not found", 404
    return send_file(
        DB_PATH, 
        as_attachment=True, 
        download_name=f"backup_{int(time.time())}.db"
    )

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(username):
    conn = get_db()
    
    # Total revenue (DONE orders)
    revenue = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status='DONE'"
    ).fetchone()[0]
    
    # Active orders
    active = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('NEW', 'PROCESSING')"
    ).fetchone()[0]
    
    # Total clients
    clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    
    # Revenue by day (last 7 days)
    now = int(time.time())
    day_seconds = 86400
    chart_data = []
    
    for i in range(6, -1, -1):
        day_start = now - ((i + 1) * day_seconds)
        day_end = now - (i * day_seconds)
        day_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status='DONE' AND created_at BETWEEN ? AND ?",
            (day_start, day_end)
        ).fetchone()[0]
        chart_data.append(day_revenue)
    
    conn.close()
    
    return jsonify({
        'revenue': revenue,
        'active_orders': active,
        'total_clients': clients,
        'chart_data': chart_data
    })

if __name__ == '__main__':
    print("🚀 Initializing Laser Workshop VK CRM...")
    init_db()
    
    # Start bot worker in background thread
    from bot_worker import start_bot
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("🤖 VK Bot worker started in background")
    
    # SSL context
    ssl_context = None
    if USE_HTTPS:
        cert_path = os.path.join(BASE_DIR, 'certs', 'cert.pem')
        key_path = os.path.join(BASE_DIR, 'certs', 'key.pem')
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = (cert_path, key_path)
            print(f"🔐 HTTPS enabled with certificates")
        else:
            print("⚠️  SSL certificates not found. Run ./generate_certs.sh first. Falling back to HTTP.")
            USE_HTTPS = False
    
    print(f"🌐 Server starting on {HOST}:{PORT}")
    print(f"📊 Access: {'https' if USE_HTTPS else 'http'}://localhost:{PORT}")
    print(f"👤 Login: admin | Password: {DEFAULT_ADMIN_PASSWORD}")
    
    app.run(
        host=HOST, 
        port=PORT, 
        ssl_context=ssl_context, 
        debug=DEBUG_MODE, 
        threaded=True
    )
