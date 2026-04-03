# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import time
import requests
import json
from threading import Thread
import datetime

# ==================== КОНФИГУРАЦИЯ (ОПТИМИЗАЦИЯ ДЛЯ PC) ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'workshop.db')
VK_TOKEN = 'YOUR_VK_TOKEN_HERE'  # Замените на ваш токен VK
VK_GROUP_ID = 'YOUR_GROUP_ID'    # Замените на ID группы

# Оптимизация для PC
MAX_CONNECTIONS = 10
AI_PROGNOSIS = True
DEBUG_MODE = True

# ==================== БАЗА ДАННЫХ (ОПТИМИЗИРОВАНО) ====================
_bot_db_pool = []

def get_db():
    """Получение соединения из пула или создание нового"""
    if _bot_db_pool:
        conn = _bot_db_pool.pop()
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
    if len(_bot_db_pool) < MAX_CONNECTIONS:
        _bot_db_pool.append(conn)
    else:
        return_db(conn)

def _precreate_bot_connections():
    """Предварительное создание пула соединений"""
    for _ in range(MAX_CONNECTIONS):
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-65536')
        conn.execute('PRAGMA busy_timeout=30000')
        conn.row_factory = sqlite3.Row
        _bot_db_pool.append(conn)

def save_vk_message(vk_id, from_user, message_text, is_admin=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vk_messages (vk_id, from_user, message_text, is_admin)
        VALUES (?, ?, ?, ?)
    ''', (vk_id, from_user, message_text, is_admin))
    # autocommit
    return_db(conn)

def get_or_create_client(vk_id, name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients WHERE vk_id = ?', (vk_id,))
    client = cursor.fetchone()
    
    if not client:
        cursor.execute('''
            INSERT INTO clients (vk_id, name) VALUES (?, ?)
        ''', (vk_id, name))
        # autocommit
        client_id = cursor.lastrowid
    else:
        client_id = client['id']
    
    return_db(conn)
    return client_id

def get_price_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM price_list')
    items = [dict(row) for row in cursor.fetchall()]
    return_db(conn)
    return items

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
        setup_price = float(params.get('setup_price', 300))
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
        material_price = float(params.get('material_price', 30))
        cut_price = float(params.get('cut_price', 30))
        material_cost = (length / 10) * (width / 10) * material_price
        cut_cost = cut_meters * cut_price
        price = material_cost + cut_cost
    
    return round(price, 2)

def apply_discount(total_price, quantity):
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

# ==================== СОСТОЯНИЕ БОТА ====================
user_states = {}

class VKBotWorker(Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.last_ts = 0
        self.running = True
        
    def run(self):
        print("🤖 VK Bot запущен в фоновом режиме...")
        while self.running:
            try:
                self.poll_messages()
            except requests.exceptions.ReadTimeout:
                print("⚠️ ReadTimeout - перезапуск LongPoll...")
                time.sleep(5)
            except Exception as e:
                print(f"❌ Ошибка бота: {e}")
                time.sleep(5)
    
    def poll_messages(self):
        url = 'https://api.vk.com/method/messages.getLongPollServer'
        params = {
            'access_token': VK_TOKEN,
            'v': '5.131'
        }
        response = requests.get(url, params=params, timeout=10)
        server_data = response.json().get('response', {})
        
        if not server_data:
            time.sleep(5)
            return
        
        longpoll_url = server_data.get('server')
        key = server_data.get('key')
        ts = server_data.get('ts', 0)
        
        while self.running:
            try:
                poll_url = f'{longpoll_url}?act=a_check&key={key}&ts={ts}&wait=25'
                poll_response = requests.get(poll_url, timeout=30)
                poll_data = poll_response.json()
                
                if 'failed' in poll_data:
                    break
                
                ts = poll_data.get('ts', ts)
                updates = poll_data.get('updates', [])
                
                for update in updates:
                    if update[0] == 4:  # Новое сообщение
                        self.handle_message(update)
                
            except requests.exceptions.ReadTimeout:
                continue
            except Exception as e:
                print(f"LongPoll Error: {e}")
                break
    
    def handle_message(self, update):
        flags = update[3]
        if flags & 2:  # Исходящее сообщение
            return
        
        vk_id = update[3] if isinstance(update[3], int) else update[1]
        message_text = update[6]
        
        # Сохраняем сообщение
        save_vk_message(vk_id, vk_id, message_text, is_admin=0)
        
        # Обрабатываем диалог
        self.process_dialog(vk_id, message_text)
    
    def process_dialog(self, vk_id, message_text):
        state = user_states.get(vk_id, {'step': 'start'})
        step = state.get('step', 'start')
        
        if step == 'start':
            # Показываем меню услуг
            price_list = get_price_list()
            menu_text = "🔧 Выберите услугу:\n\n"
            keyboard = []
            
            for i, item in enumerate(price_list):
                menu_text += f"{i+1}. {item['name']} - {item['price']}₽\n"
                keyboard.append(str(i+1))
            
            menu_text += "\nВведите номер услуги:"
            vk_send_message(vk_id, menu_text)
            user_states[vk_id] = {'step': 'select_service', 'price_list': price_list}
            
        elif step == 'select_service':
            try:
                service_idx = int(message_text) - 1
                price_list = state.get('price_list', get_price_list())
                
                if 0 <= service_idx < len(price_list):
                    service = price_list[service_idx]
                    user_states[vk_id] = {
                        'step': 'collect_params',
                        'service': service,
                        'params': {}
                    }
                    
                    # Запрашиваем параметры в зависимости от типа
                    self.request_params(vk_id, service)
                else:
                    vk_send_message(vk_id, "❌ Неверный номер. Попробуйте снова:")
            except ValueError:
                vk_send_message(vk_id, "❌ Введите число:")
        
        elif step == 'collect_params':
            service = state.get('service', {})
            params = state.get('params', {})
            calc_type = service.get('calc_type', 'fixed')
            
            # Собираем параметры по шагам
            self.collect_param_step(vk_id, message_text, service, params, calc_type)
    
    def request_params(self, vk_id, service):
        calc_type = service.get('calc_type', 'fixed')
        param_requests = {
            'fixed': 'Введите количество (шт):',
            'area_cm2': 'Введите длину (см):',
            'meter_thickness': 'Введите длину реза (метры):',
            'per_minute': 'Введите время работы (минуты):',
            'per_char': 'Введите количество символов:',
            'vector_length': 'Введите длину вектора (метры):',
            'setup_batch': 'Введите тираж (шт):',
            'photo_raster': 'Введите длину (см):',
            'cylindrical': 'Введите диаметр (мм):',
            'volume_3d': 'Введите длину (см):',
            'material_and_cut': 'Введите длину материала (см):'
        }
        
        vk_send_message(vk_id, param_requests.get(calc_type, 'Введите параметры:'))
    
    def collect_param_step(self, vk_id, message_text, service, params, calc_type):
        current_param = service.get('calc_type', 'fixed')
        
        # Упрощенная логика - собираем все параметры последовательно
        if current_param == 'fixed':
            params['quantity'] = int(message_text) if message_text.isdigit() else 1
        elif current_param == 'area_cm2':
            if 'length' not in params:
                params['length'] = float(message_text)
                vk_send_message(vk_id, "Введите ширину (см):")
                user_states[vk_id]['params'] = params
                return
            else:
                params['width'] = float(message_text)
        elif current_param == 'meter_thickness':
            if 'meters' not in params:
                params['meters'] = float(message_text)
                vk_send_message(vk_id, "Введите толщину (мм):")
                user_states[vk_id]['params'] = params
                return
            else:
                params['thickness'] = float(message_text)
        elif current_param == 'per_minute':
            params['minutes'] = float(message_text)
        elif current_param == 'per_char':
            params['chars'] = int(message_text) if message_text.isdigit() else 0
        elif current_param == 'vector_length':
            params['length'] = float(message_text)
        elif current_param == 'setup_batch':
            params['quantity'] = int(message_text) if message_text.isdigit() else 1
        elif current_param == 'photo_raster':
            if 'length' not in params:
                params['length'] = float(message_text)
                vk_send_message(vk_id, "Введите ширину (см):")
                user_states[vk_id]['params'] = params
                return
            else:
                params['width'] = float(message_text)
        elif current_param == 'cylindrical':
            if 'diameter' not in params:
                params['diameter'] = float(message_text)
                vk_send_message(vk_id, "Введите длину (мм):")
                user_states[vk_id]['params'] = params
                return
            else:
                params['length'] = float(message_text)
        elif current_param == 'volume_3d':
            if 'length' not in params:
                params['length'] = float(message_text)
                vk_send_message(vk_id, "Введите ширину (см):")
                user_states[vk_id]['params'] = params
                return
            elif 'width' not in params:
                params['width'] = float(message_text)
                vk_send_message(vk_id, "Введите глубину (мм):")
                user_states[vk_id]['params'] = params
                return
            else:
                params['depth'] = float(message_text)
        elif current_param == 'material_and_cut':
            if 'length' not in params:
                params['length'] = float(message_text)
                vk_send_message(vk_id, "Введите ширину (см):")
                user_states[vk_id]['params'] = params
                return
            elif 'width' not in params:
                params['width'] = float(message_text)
                vk_send_message(vk_id, "Введите метры реза:")
                user_states[vk_id]['params'] = params
                return
            else:
                params['cut_meters'] = float(message_text)
        
        # Расчет итоговой цены
        base_price = service.get('price', 0)
        total_price = calculate_price(current_param, params, base_price)
        
        # Получаем количество для скидки
        quantity = params.get('quantity', 1)
        final_price, discount_percent = apply_discount(total_price, quantity)
        
        # Сохраняем заказ
        self.save_order(vk_id, service, params, final_price, discount_percent)
        
        # Отправляем подтверждение
        confirm_text = f"✅ Заказ оформлен!\n"
        confirm_text += f"Услуга: {service['name']}\n"
        confirm_text += f"Сумма: {final_price}₽"
        if discount_percent > 0:
            confirm_text += f" (скидка {discount_percent}%)\n"
        confirm_text += "\nМенеджер свяжется с вами."
        
        vk_send_message(vk_id, confirm_text)
        
        # Сбрасываем состояние
        user_states[vk_id] = {'step': 'start'}
    
    def save_order(self, vk_id, service, params, total_price, discount):
        client_id = get_or_create_client(vk_id, f"VK User {vk_id}")
        
        params_text = "; ".join([f"{k}: {v}" for k, v in params.items()])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (client_id, vk_id, client_name, service_id, service_name,
                               description, parameters, total_price, discount, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            client_id, vk_id, f"VK User {vk_id}", service['id'], service['name'],
            service['name'], params_text, total_price, discount, 'NEW'
        ))
        # autocommit
        return_db(conn)

# ==================== ЗАПУСК (ОПТИМИЗИРОВАН) ====================
if __name__ == '__main__':
    # Предварительное создание пула соединений для быстрого старта
    _precreate_bot_connections()
    print(f"✅ Пул соединений бота создан: {MAX_CONNECTIONS} соединений")
    
    bot = VKBotWorker()
    bot.start()
    
    print("🤖 VK Бот запущен и готов к работе")
    print(f"⚡ Оптимизация: MAX_CONNECTIONS={MAX_CONNECTIONS}, AI={'ON' if AI_PROGNOSIS else 'OFF'}")
    
    # Держим основной поток активным
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.running = False
        print("🛑 Бот остановлен")