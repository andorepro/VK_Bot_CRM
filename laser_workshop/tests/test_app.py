# -*- coding: utf-8 -*-
"""
Модульные тесты для приложения Laser Workshop
"""
import pytest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем приложение и функции
from app import (
    app as flask_app,
    ConnectionPool,
    LRUCache,
    calculate_price,
    apply_discount,
    validate_promo_code,
    use_promo_code,
    add_cashback,
    use_cashback,
    update_client_stats,
    deduct_inventory,
    check_low_stock,
    generate_token,
    verify_token,
    log_audit,
    save_vk_message,
    save_notification,
    calculate_cdek_delivery,
    create_yookassa_payment,
    db_pool,
    DB_PATH,
    SECRET_KEY
)


# Helper function for tests
def get_db_for_tests():
    """Вспомогательная функция для получения соединения с БД в тестах"""
    return db_pool.get_connection().__enter__()


# ==================== ФИКСТУРЫ ====================

@pytest.fixture
def test_db_path():
    """Создание временной БД для тестов"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def app(test_db_path):
    """Фикстура Flask приложения с тестовой БД"""
    # Патчим пути к БД
    with patch('app.DB_PATH', test_db_path):
        with patch('app.db_pool', ConnectionPool(test_db_path, max_connections=5)):
            flask_app.config['TESTING'] = True
            flask_app.config['SECRET_KEY'] = 'test_secret_key'
            with flask_app.app_context():
                # Инициализируем схему БД
                conn = sqlite3.connect(test_db_path)
                cursor = conn.cursor()
                
                # Создаем все необходимые таблицы
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'manager',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
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
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
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
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory_operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_id INTEGER,
                        operation_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        order_id INTEGER,
                        user_id INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cashback_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id INTEGER,
                        order_id INTEGER,
                        amount REAL NOT NULL,
                        operation_type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
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
                
                # Добавляем тестовые данные
                cursor.execute("INSERT INTO price_list (name, calc_type, price, description) VALUES (?, ?, ?, ?)",
                              ('Тестовая услуга', 'fixed', 100.0, 'Тест'))
                
                cursor.execute("INSERT INTO promo_codes (code, discount_percent, max_uses, current_uses, is_active) VALUES (?, ?, ?, ?, ?)",
                              ('TEST10', 10.0, 100, 0, 1))
                
                cursor.execute("INSERT INTO promo_codes (code, discount_percent, max_uses, current_uses, is_active, valid_until) VALUES (?, ?, ?, ?, ?, ?)",
                              ('EXPIRED', 20.0, 100, 0, 1, '2020-01-01'))
                
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                              ('testuser', 'hash123', 'manager'))
                
                cursor.execute("INSERT INTO clients (vk_id, name, cashback_balance, cashback_earned) VALUES (?, ?, ?, ?)",
                              (12345, 'Test Client', 500.0, 500.0))
                
                cursor.execute("INSERT INTO inventory (item_name, item_type, quantity, unit, min_quantity, price_per_unit, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              ('Тестовый товар', 'material', 50, 'шт', 10, 100.0, 1))
                
                cursor.execute("INSERT INTO inventory (item_name, item_type, quantity, unit, min_quantity, price_per_unit, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              ('Мало товара', 'material', 5, 'шт', 10, 100.0, 1))
                
                conn.commit()
                conn.close()
                
                yield flask_app


@pytest.fixture
def client(app, test_db_path):
    """Тестовый клиент Flask"""
    with patch('app.DB_PATH', test_db_path):
        with app.test_client() as test_client:
            yield test_client


@pytest.fixture
def auth_client(client):
    """Клиент с авторизацией"""
    token = generate_token('testuser', 'manager')
    client.set_cookie('localhost', 'auth_token', token)
    return client


# ==================== ТЕСТЫ CONNECTIONPOOL ====================

class TestConnectionPool:
    """Тесты для пула соединений с БД"""
    
    def test_pool_creation(self, test_db_path):
        """Тест создания пула соединений"""
        pool = ConnectionPool(test_db_path, max_connections=3)
        assert pool.max_connections == 3
        assert pool.db_path == test_db_path
        assert len(pool._pool) == 0
    
    def test_get_connection(self, test_db_path):
        """Тест получения соединения из пула"""
        pool = ConnectionPool(test_db_path, max_connections=3)
        
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result[0] == 1
        
        # После выхода из контекста соединение должно вернуться в пул
        assert len(pool._pool) == 1
    
    def test_connection_reuse(self, test_db_path):
        """Тест повторного использования соединений"""
        pool = ConnectionPool(test_db_path, max_connections=3)
        
        # Первое получение
        with pool.get_connection() as conn1:
            conn1_id = id(conn1)
        
        # Второе получение (должно вернуть то же соединение)
        with pool.get_connection() as conn2:
            conn2_id = id(conn2)
        
        assert conn1_id == conn2_id
    
    def test_pool_max_size(self, test_db_path):
        """Тест ограничения размера пула"""
        pool = ConnectionPool(test_db_path, max_connections=2)
        connections = []
        
        # Открываем больше соединений чем максимум в пуле
        for _ in range(5):
            ctx = pool.get_connection()
            conn = ctx.__enter__()
            connections.append((ctx, conn))
        
        # Закрываем все соединения
        for ctx, conn in connections:
            ctx.__exit__(None, None, None)
        
        # В пуле должно быть не больше max_connections
        assert len(pool._pool) <= pool.max_connections


# ==================== ТЕСТЫ LRUCACHE ====================

class TestLRUCache:
    """Тесты для LRU кэша"""
    
    def test_cache_set_get(self):
        """Тест записи и чтения из кэша"""
        cache = LRUCache(max_size=5, ttl=300)
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
    
    def test_cache_max_size(self):
        """Тест ограничения размера кэша"""
        cache = LRUCache(max_size=3, ttl=300)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        cache.set('key4', 'value4')  # Должен вытеснить key1
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key4') == 'value4'
    
    def test_cache_ttl(self):
        """Тест времени жизни кэша"""
        cache = LRUCache(max_size=5, ttl=0.1)  # 100мс TTL
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        
        import time
        time.sleep(0.2)  # Ждем истечения TTL
        
        assert cache.get('key1') is None
    
    def test_cache_invalidate(self):
        """Тест инвалидации ключа"""
        cache = LRUCache(max_size=5, ttl=300)
        
        cache.set('key1', 'value1')
        cache.invalidate('key1')
        
        assert cache.get('key1') is None
    
    def test_cache_clear_pattern(self):
        """Тест очистки по паттерну"""
        cache = LRUCache(max_size=10, ttl=300)
        
        cache.set('user_1', 'data1')
        cache.set('user_2', 'data2')
        cache.set('product_1', 'data3')
        
        cache.clear_pattern('user_')
        
        assert cache.get('user_1') is None
        assert cache.get('user_2') is None
        assert cache.get('product_1') == 'data3'
    
    def test_cache_lru_order(self):
        """Тест LRU порядка доступа"""
        cache = LRUCache(max_size=3, ttl=300)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Доступ к key1 перемещает его в конец
        cache.get('key1')
        
        # Добавление нового ключа должно вытеснить key2 (самый старый)
        cache.set('key4', 'value4')
        
        assert cache.get('key2') is None
        assert cache.get('key1') == 'value1'


# ==================== ТЕСТЫ КАЛЬКУЛЯТОРА ====================

class TestCalculatePrice:
    """Тесты для функции расчета стоимости"""
    
    def test_fixed_price(self):
        """Тест фиксированной цены"""
        params = {'quantity': 5}
        result = calculate_price('fixed', params, 100.0)
        assert result == 500.0
    
    def test_fixed_price_default_quantity(self):
        """Тест фиксированной цены с количеством по умолчанию"""
        params = {}
        result = calculate_price('fixed', params, 100.0)
        assert result == 100.0
    
    def test_area_cm2(self):
        """Тест расчета по площади (см²)"""
        params = {'length': 100, 'width': 100}  # 100мм x 100мм = 100см²
        result = calculate_price('area_cm2', params, 15.0)
        assert result == 1500.0  # 100см² * 15
    
    def test_meter_thickness(self):
        """Тест расчета резки по метрам и толщине"""
        params = {'meters': 10, 'thickness': 6}  # 10м * толщина 6мм
        result = calculate_price('meter_thickness', params, 25.0)
        assert result == 500.0  # 10 * (25 * (6/3)) = 10 * 50
    
    def test_per_minute(self):
        """Тест расчета по минутам"""
        params = {'minutes': 30}
        result = calculate_price('per_minute', params, 100.0)
        assert result == 3000.0
    
    def test_per_char(self):
        """Тест расчета по символам"""
        params = {'chars': 50}
        result = calculate_price('per_char', params, 50.0)
        assert result == 2500.0
    
    def test_vector_length(self):
        """Тест расчета по длине вектора"""
        params = {'length': 25.5}
        result = calculate_price('vector_length', params, 80.0)
        assert result == 2040.0
    
    def test_setup_batch(self):
        """Тест расчета настройки + тираж"""
        params = {'setup_price': 300, 'unit_price': 50, 'quantity': 10}
        result = calculate_price('setup_batch', params, 300.0)
        assert result == 800.0  # 300 + (50 * 10)
    
    def test_photo_raster(self):
        """Тест расчета фото гравировки"""
        params = {'length': 100, 'width': 100, 'dpi_multiplier': 2.0}
        result = calculate_price('photo_raster', params, 20.0)
        assert result == 400.0  # 10см * 10см * 20 * 2.0
    
    def test_cylindrical(self):
        """Тест расчета цилиндрической гравировки"""
        params = {'diameter': 70, 'length': 100}  # Термос диаметр 70мм
        result = calculate_price('cylindrical', params, 35.0)
        # (70 * 3.14 * 100) / 100 * 35 = 219.8 * 35 = 7693
        assert abs(result - 7693.0) < 1
    
    def test_volume_3d(self):
        """Тест расчета 3D клише"""
        params = {'length': 100, 'width': 100, 'depth': 5}
        result = calculate_price('volume_3d', params, 45.0)
        assert result == 2250.0  # 10см * 10см * 5 * 45
    
    def test_material_and_cut(self):
        """Тест расчета материал + резка"""
        params = {
            'length': 100, 'width': 100, 'cut_meters': 5,
            'material_price': 30, 'cut_price': 25
        }
        result = calculate_price('material_and_cut', params, 30.0)
        assert result == 425.0  # (10*10*30) + (5*25) = 300 + 125
    
    def test_unknown_calc_type(self):
        """Тест неизвестного типа расчета"""
        params = {}
        result = calculate_price('unknown_type', params, 100.0)
        assert result == 0.0


# ==================== ТЕСТЫ СКИДОК И ПРОМОКОДОВ ====================

class TestDiscounts:
    """Тесты для системы скидок"""
    
    def test_no_discount(self):
        """Тест без скидки"""
        result, discount_pct, source, cashback_used = apply_discount(1000, 5)
        assert discount_pct == 0
        assert source == 'quantity'
        assert result == 1000
    
    def test_quantity_discount_10(self):
        """Тест скидки за количество 10+"""
        result, discount_pct, source, _ = apply_discount(1000, 10)
        assert discount_pct == 5
        assert result == 950
    
    def test_quantity_discount_20(self):
        """Тест скидки за количество 20+"""
        result, discount_pct, source, _ = apply_discount(1000, 20)
        assert discount_pct == 10
        assert result == 900
    
    def test_quantity_discount_50(self):
        """Тест скидки за количество 50+"""
        result, discount_pct, source, _ = apply_discount(1000, 50)
        assert discount_pct == 15
        assert result == 850
    
    def test_quantity_discount_100(self):
        """Тест скидки за количество 100+"""
        result, discount_pct, source, _ = apply_discount(1000, 100)
        assert discount_pct == 20
        assert result == 800
    
    def test_cashback_application(self):
        """Тест применения кэшбека"""
        result, _, _, cashback_used = apply_discount(1000, 5, cashback_balance=500)
        # Максимум 30% от суммы = 300
        assert cashback_used == 300
        assert result == 700
    
    def test_cashback_limit(self):
        """Тест ограничения кэшбека"""
        result, _, _, cashback_used = apply_discount(1000, 5, cashback_balance=100)
        # Кэшбек меньше 30%, применяем полностью
        assert cashback_used == 100
        assert result == 900


# ==================== ТЕСТЫ JWT ТОКЕНОВ ====================

class TestJWT:
    """Тесты для JWT токенов"""
    
    def test_generate_token(self):
        """Тест генерации токена"""
        token = generate_token('testuser', 'manager')
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_token(self):
        """Тест проверки валидного токена"""
        token = generate_token('testuser', 'admin')
        payload = verify_token(token)
        
        assert payload is not None
        assert payload['username'] == 'testuser'
        assert payload['role'] == 'admin'
    
    def test_verify_expired_token(self):
        """Тест проверки истекшего токена"""
        with patch('app.datetime') as mock_datetime:
            # Создаем токен с прошедшим временем
            mock_datetime.datetime.now.return_value = datetime.now() - timedelta(days=8)
            mock_datetime.timedelta = timedelta
            
            token = generate_token('testuser', 'manager')
        
        # Токен должен быть невалидным
        payload = verify_token(token)
        assert payload is None
    
    def test_verify_invalid_token(self):
        """Тест проверки невалидного токена"""
        result = verify_token('invalid.token.here')
        assert result is None
    
    def test_token_contains_role(self):
        """Тест что токен содержит роль"""
        token = generate_token('master1', 'master')
        payload = verify_token(token)
        assert payload['role'] == 'master'


# ==================== ТЕСТЫ API ENDPOINTS ====================

class TestAPIEndpoints:
    """Тесты для API эндпоинтов"""
    
    def test_price_list_endpoint(self, auth_client):
        """Тест получения прайс-листа"""
        response = auth_client.get('/api/price_list')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_price_list_unauthorized(self, client):
        """Тест доступа к прайс-листу без авторизации"""
        response = client.get('/api/price_list')
        assert response.status_code == 302  # Редирект на логин
    
    def test_promo_validation_endpoint(self, auth_client):
        """Тест валидации промокода"""
        response = auth_client.post('/api/validate_promo', 
                                    json={'code': 'TEST10'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['valid'] is True
        assert data['discount'] == 10
    
    def test_promo_validation_invalid(self, auth_client):
        """Тест валидации несуществующего промокода"""
        response = auth_client.post('/api/validate_promo',
                                    json={'code': 'INVALID'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['valid'] is False
    
    def test_create_order_endpoint(self, auth_client):
        """Тест создания заказа"""
        order_data = {
            'client_id': 1,
            'service_id': 1,
            'description': 'Тестовый заказ',
            'parameters': '{"quantity": 1}',
            'total_price': 1000.0
        }
        response = auth_client.post('/api/orders',
                                    json=order_data,
                                    content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'order_id' in data
    
    def test_get_orders_endpoint(self, auth_client):
        """Тест получения списка заказов"""
        response = auth_client.get('/api/orders')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_get_clients_endpoint(self, auth_client):
        """Тест получения списка клиентов"""
        response = auth_client.get('/api/clients')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_update_order_status(self, auth_client, test_db_path):
        """Тест обновления статуса заказа"""
        # Сначала создаем заказ
        with patch('app.DB_PATH', test_db_path):
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders (client_id, description, parameters, total_price, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (1, 'Test', '{}', 100.0, 'NEW'))
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()
        
        response = auth_client.put('/api/orders/status',
                                   json={'order_id': order_id, 'status': 'IN_PROGRESS'})
        assert response.status_code == 200


# ==================== ТЕСТЫ СКЛАДА ====================

class TestInventory:
    """Тесты для складской системы"""
    
    def test_check_low_stock(self, test_db_path):
        """Тест проверки товаров с низким остатком"""
        with patch('app.DB_PATH', test_db_path):
            low_stock = check_low_stock()
            assert isinstance(low_stock, list)
            # У нас есть один товар "Мало товара" с quantity=5 < min_quantity=10
            assert len(low_stock) >= 1
    
    def test_deduct_inventory_success(self, test_db_path):
        """Тест успешного списания со склада"""
        with patch('app.DB_PATH', test_db_path):
            # Получаем начальный остаток
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT quantity FROM inventory WHERE item_name = ?', ('Тестовый товар',))
            initial_qty = cursor.fetchone()[0]
            
            # Списываем товар
            deduct_inventory('Тестовый товар', {'quantity': 10})
            
            # Проверяем новый остаток
            cursor.execute('SELECT quantity FROM inventory WHERE item_name = ?', ('Тестовый товар',))
            new_qty = cursor.fetchone()[0]
            
            assert new_qty == initial_qty - 10
            conn.close()


# ==================== ТЕСТЫ КЭШБЕКА ====================

class TestCashback:
    """Тесты для системы кэшбека"""
    
    def test_add_cashback(self, test_db_path):
        """Тест начисления кэшбека"""
        with patch('app.DB_PATH', test_db_path):
            # Получаем начальный баланс
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT cashback_balance FROM clients WHERE vk_id = ?', (12345,))
            initial_balance = cursor.fetchone()[0]
            
            # Начисляем кэшбек
            add_cashback(1, 1, 1000.0)  # 5% от 1000 = 50
            
            # Проверяем новый баланс
            cursor.execute('SELECT cashback_balance FROM clients WHERE vk_id = ?', (12345,))
            new_balance = cursor.fetchone()[0]
            
            assert new_balance == initial_balance + 50.0
            conn.close()
    
    def test_use_cashback(self, test_db_path):
        """Тест использования кэшбека"""
        with patch('app.DB_PATH', test_db_path):
            # Получаем начальный баланс
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT cashback_balance FROM clients WHERE vk_id = ?', (12345,))
            initial_balance = cursor.fetchone()[0]
            
            # Используем кэшбек
            success, remaining = use_cashback(1, 100.0)
            
            assert success is True
            assert remaining == initial_balance - 100.0
            conn.close()
    
    def test_use_cashback_insufficient(self, test_db_path):
        """Тест недостаточного кэшбека"""
        with patch('app.DB_PATH', test_db_path):
            success, remaining = use_cashback(1, 10000.0)  # Больше чем есть
            assert success is False


# ==================== ТЕСТЫ АУДИТА ====================

class TestAudit:
    """Тесты для системы аудита"""
    
    def test_log_audit(self, test_db_path):
        """Тест записи в аудит лог"""
        with patch('app.DB_PATH', test_db_path):
            log_audit(
                user_id=1,
                action='test_action',
                entity_type='order',
                entity_id=123,
                old_value='{"status": "NEW"}',
                new_value='{"status": "DONE"}',
                ip_address='127.0.0.1'
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM audit_log WHERE action = ?', ('test_action',))
            count = cursor.fetchone()[0]
            
            assert count == 1
            conn.close()


# ==================== ТЕСТЫ УВЕДОМЛЕНИЙ ====================

class TestNotifications:
    """Тесты для системы уведомлений"""
    
    def test_save_notification(self, test_db_path):
        """Тест сохранения уведомления"""
        with patch('app.DB_PATH', test_db_path):
            save_notification(
                order_id=1,
                vk_id=12345,
                message_text='Ваш заказ готов',
                status='pending'
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM notifications WHERE order_id = ?', (1,))
            count = cursor.fetchone()[0]
            
            assert count == 1
            conn.close()
    
    def test_save_vk_message(self, test_db_path):
        """Тест сохранения VK сообщения"""
        with patch('app.DB_PATH', test_db_path):
            save_vk_message(
                vk_id=12345,
                from_user=67890,
                message_text='Привет!',
                is_admin=0
            )
            
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM vk_messages WHERE vk_id = ?', (12345,))
            count = cursor.fetchone()[0]
            
            assert count == 1
            conn.close()


# ==================== ТЕСТЫ ИНТЕГРАЦИЙ ====================

class TestIntegrations:
    """Тесты для внешних интеграций"""
    
    def test_calculate_cdek_delivery(self):
        """Тест расчета доставки СДЭК"""
        result = calculate_cdek_delivery(1.0, 'Москва', 'СПб')
        assert isinstance(result, float)
        assert result > 0
    
    def test_create_yookassa_payment(self):
        """Тест создания платежа ЮKassa"""
        result = create_yookassa_payment(1000.0, 1, 12345)
        assert result['success'] is True
        assert 'payment_id' in result
        assert 'confirmation_url' in result


# ==================== ЗАПУСК ТЕСТОВ ====================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
