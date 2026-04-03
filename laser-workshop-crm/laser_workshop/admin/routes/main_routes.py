# -*- coding: utf-8 -*-
"""
Маршруты админ панели Flask
Аутентификация, дашборд, заказы, клиенты
"""

from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from functools import wraps

# Создание blueprint для разных разделов
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
orders_bp = Blueprint('orders', __name__, url_prefix='/orders')
clients_bp = Blueprint('clients', __name__, url_prefix='/clients')
services_bp = Blueprint('services', __name__, url_prefix='/services')
stock_bp = Blueprint('stock', __name__, url_prefix='/stock')
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
api_bp = Blueprint('api', __name__, url_prefix='/api')


# ==================== ДЕКОРАТОРЫ ====================

def login_required(f):
    """Декоратор проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Декоратор проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== АУТЕНТИФИКАЦИЯ ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # TODO: Реальная проверка в БД
        if username and password:
            session['user_id'] = 1
            session['username'] = username
            session['role'] = 'admin'
            return redirect(url_for('dashboard.index'))
        
        return render_template('admin/login.html', error='Неверный логин или пароль')
    
    return render_template('admin/login.html')


@auth_bp.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    return redirect(url_for('auth.login'))


# ==================== ДАШБОРД ====================

@dashboard_bp.route('/')
@login_required
def index():
    """Главная страница дашборда"""
    stats = {
        'total_orders': 0,
        'new_orders': 0,
        'total_clients': 0,
        'revenue_today': 0
    }
    return render_template('admin/dashboard.html', stats=stats)


# ==================== ЗАКАЗЫ ====================

@orders_bp.route('/')
@login_required
def orders_list():
    """Список всех заказов"""
    return render_template('admin/orders/list.html')


@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    """Детали заказа"""
    return render_template('admin/orders/detail.html', order_id=order_id)


@orders_bp.route('/create', methods=['GET', 'POST'])
@login_required
def order_create():
    """Создание нового заказа"""
    if request.method == 'POST':
        # TODO: Сохранение заказа в БД
        return redirect(url_for('orders.orders_list'))
    
    return render_template('admin/orders/form.html')


@orders_bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def order_edit(order_id):
    """Редактирование заказа"""
    return render_template('admin/orders/form.html', order_id=order_id)


@orders_bp.route('/<int:order_id>/delete', methods=['POST'])
@login_required
def order_delete(order_id):
    """Удаление заказа"""
    # TODO: Удаление из БД
    return redirect(url_for('orders.orders_list'))


# ==================== КЛИЕНТЫ ====================

@clients_bp.route('/')
@login_required
def clients_list():
    """Список клиентов"""
    return render_template('admin/clients/list.html')


@clients_bp.route('/<int:client_id>')
@login_required
def client_detail(client_id):
    """Детали клиента"""
    return render_template('admin/clients/detail.html', client_id=client_id)


# ==================== API ====================

@api_bp.route('/orders', methods=['GET'])
@login_required
def api_orders():
    """API получения заказов"""
    return jsonify({'orders': []})


@api_bp.route('/clients', methods=['GET'])
@login_required
def api_clients():
    """API получения клиентов"""
    return jsonify({'clients': []})


@api_bp.route('/stats', methods=['GET'])
@login_required
def api_stats():
    """API статистики"""
    return jsonify({
        'total_orders': 0,
        'new_orders': 0,
        'total_clients': 0,
        'revenue': 0
    })
