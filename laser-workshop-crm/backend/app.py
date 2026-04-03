"""
Flask приложение - основной сервер
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import json
from datetime import datetime

from core.config import SECRET_KEY, DEBUG, HOST, PORT, DB_PATH, BACKUP_DIR
from core.models.database import init_db, get_db_connection
from core.services.order_service import OrderService
from core.services.calculator import Calculator

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Инициализация БД при старте
init_db()

# ==================== WEB ИНТЕРФЕЙС ====================

@app.route('/')
def index():
    """Главная страница - дашборд"""
    return render_template('dashboard.html')

@app.route('/orders')
def orders_page():
    """Страница заказов"""
    return render_template('orders.html')

@app.route('/clients')
def clients_page():
    """Страница клиентов"""
    return render_template('clients.html')

@app.route('/chat')
def chat_page():
    """Страница чата VK"""
    return render_template('chat.html')

@app.route('/analytics')
def analytics_page():
    """Страница аналитики"""
    return render_template('analytics.html')

@app.route('/settings')
def settings_page():
    """Страница настроек"""
    return render_template('settings.html')

# ==================== API ЗАКАЗЫ ====================

@app.route('/api/orders', methods=['GET'])
def api_get_orders():
    """Получение списка заказов"""
    status = request.args.get('status')
    search = request.args.get('search')
    limit = int(request.args.get('limit', 50))
    
    orders = OrderService.get_orders(status=status, search_query=search, limit=limit)
    return jsonify({'success': True, 'orders': orders})

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def api_get_order(order_id):
    """Получение заказа по ID"""
    order = OrderService.get_order_by_id(order_id)
    if order:
        return jsonify({'success': True, 'order': order})
    return jsonify({'success': False, 'error': 'Заказ не найден'}), 404

@app.route('/api/orders', methods=['POST'])
def api_create_order():
    """Создание нового заказа"""
    data = request.json
    
    try:
        result = OrderService.create_order(
            client_id=data['client_id'],
            service_id=data['service_id'],
            parameters=data.get('parameters', {}),
            quantity=data.get('quantity', 1),
            priority=data.get('priority', 'normal'),
            promo_code=data.get('promo_code')
        )
        return jsonify({'success': True, 'order': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def api_update_order_status(order_id):
    """Обновление статуса заказа"""
    data = request.json
    new_status = data.get('status')
    comment = data.get('comment', '')
    
    if not new_status:
        return jsonify({'success': False, 'error': 'Статус не указан'}), 400
    
    success = OrderService.update_status(order_id, new_status, comment)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Ошибка обновления'}), 400

@app.route('/api/orders/<int:order_id>/history', methods=['GET'])
def api_get_order_history(order_id):
    """История изменений заказа"""
    history = OrderService.get_order_history(order_id)
    return jsonify({'success': True, 'history': history})

# ==================== API КЛИЕНТЫ ====================

@app.route('/api/clients', methods=['GET'])
def api_get_clients():
    """Получение списка клиентов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM clients 
        ORDER BY total_spent DESC 
        LIMIT 100
    ''')
    
    clients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'clients': clients})

@app.route('/api/clients/<int:client_id>', methods=['GET'])
def api_get_client(client_id):
    """Получение клиента по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    conn.close()
    
    if client:
        return jsonify({'success': True, 'client': dict(client)})
    return jsonify({'success': False, 'error': 'Клиент не найден'}), 404

# ==================== API УСЛУГИ ====================

@app.route('/api/services', methods=['GET'])
def api_get_services():
    """Получение списка услуг (без указания станков для клиентов)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, calc_type, base_price, description FROM services WHERE is_active = 1')
    services = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'services': services})

# ==================== API КАЛЬКУЛЯТОР ====================

@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    """Расчёт стоимости заказа"""
    data = request.json
    
    try:
        price = Calculator.calculate(data['calc_type'], data['params'])
        
        # Применяем оптовую скидку если нужно
        quantity = data.get('quantity', 1)
        if quantity >= 10:
            price = Calculator.apply_bulk_discount(price, quantity)
        
        return jsonify({
            'success': True,
            'price': round(price, 2),
            'quantity': quantity
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ==================== API СТАТИСТИКА ====================

@app.route('/api/stats/dashboard', methods=['GET'])
def api_get_dashboard_stats():
    """Статистика для дашборда"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Всего заказов
    cursor.execute('SELECT COUNT(*) as count FROM orders')
    total_orders = cursor.fetchone()['count']
    
    # Заказов в работе
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'processing'")
    processing_orders = cursor.fetchone()['count']
    
    # Готовых заказов
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'done'")
    done_orders = cursor.fetchone()['count']
    
    # Выручка за месяц
    cursor.execute('''
        SELECT SUM(final_price) as revenue 
        FROM orders 
        WHERE status IN ('done', 'delivered')
        AND created_at >= date('now', '-30 days')
    ''')
    revenue = cursor.fetchone()['revenue'] or 0
    
    # Топ услуг
    cursor.execute('''
        SELECT s.name, COUNT(o.id) as count 
        FROM orders o
        JOIN services s ON o.service_id = s.id
        GROUP BY o.service_id
        ORDER BY count DESC
        LIMIT 5
    ''')
    top_services = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_orders': total_orders,
            'processing_orders': processing_orders,
            'done_orders': done_orders,
            'revenue': round(revenue, 2),
            'top_services': top_services
        }
    })

@app.route('/api/stats/revenue', methods=['GET'])
def api_get_revenue_stats():
    """Статистика выручки по дням"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DATE(created_at) as date, SUM(final_price) as revenue
        FROM orders
        WHERE status IN ('done', 'delivered')
        AND created_at >= date('now', '-30 days')
        GROUP BY DATE(created_at)
        ORDER BY date
    ''')
    
    stats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'data': stats})

# ==================== ЭКСПОРТ ====================

@app.route('/api/export/orders', methods=['GET'])
def api_export_orders():
    """Экспорт заказов в CSV"""
    import csv
    import io
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT o.id, c.name as client, s.name as service, o.status, 
               o.quantity, o.final_price, o.created_at
        FROM orders o
        JOIN clients c ON o.client_id = c.id
        JOIN services s ON o.service_id = s.id
        ORDER BY o.created_at DESC
    ''')
    
    orders = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Клиент', 'Услуга', 'Статус', 'Кол-во', 'Цена', 'Дата'])
    
    for order in orders:
        writer.writerow([
            order['id'], order['client'], order['service'],
            order['status'], order['quantity'], order['final_price'],
            order['created_at']
        ])
    
    output.seek(0)
    
    filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

# ==================== БЭКАПЫ ====================

@app.route('/api/backup/create', methods=['POST'])
def api_create_backup():
    """Создание бэкапа БД"""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"laser_workshop_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    # Создаем директорию бэкапов если нет
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Копируем БД
    shutil.copy(DB_PATH, backup_path)
    
    return jsonify({
        'success': True,
        'backup_file': backup_filename,
        'backup_path': backup_path
    })

@app.route('/api/backup/list', methods=['GET'])
def api_list_backups():
    """Список бэкапов"""
    if not os.path.exists(BACKUP_DIR):
        return jsonify({'success': True, 'backups': []})
    
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')],
        reverse=True
    )
    
    return jsonify({'success': True, 'backups': backups})

@app.route('/api/backup/download/<filename>', methods=['GET'])
def api_download_backup(filename):
    """Скачивание бэкапа"""
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    if os.path.exists(backup_path):
        return send_file(backup_path, as_attachment=True)
    return jsonify({'success': False, 'error': 'Бэкап не найден'}), 404

# ==================== НАСТРОЙКИ ====================

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Получение настроек"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT key, value FROM settings')
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    
    return jsonify({'success': True, 'settings': settings})

@app.route('/api/settings', methods=['PUT'])
def api_update_settings():
    """Обновление настроек"""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for key, value in data.items():
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        ''', (key, str(value)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    print("🚀 Запуск Laser Workshop CRM...")
    print(f"📊 Web-интерфейс: http://{HOST}:{PORT}")
    print(f"💾 База данных: {DB_PATH}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
