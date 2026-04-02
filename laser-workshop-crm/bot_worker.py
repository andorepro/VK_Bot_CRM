# -*- coding: utf-8 -*-
"""
🤖 VK Bot Worker для Лазерная Мастерская CRM (Фаза 3)
- LongPoll интеграция с ВКонтакте
- 11 алгоритмов расчёта стоимости
- Система промокодов и кэшбека
- Автосохранение заказов в БД
- Обработка ошибок и перезапуск
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import time
import requests
import json
from threading import Thread
import datetime

# ==================== КОНФИГУРАЦИЯ ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'workshop.db')

# Загрузка из .env или значения по умолчанию
def get_env(key, default):
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    k, v = line.strip().split('=', 1)
                    if k == key:
                        return v
    return default

VK_TOKEN = get_env('VK_TOKEN', 'YOUR_VK_TOKEN_HERE')
VK_GROUP_ID = get_env('VK_GROUP_ID', 'YOUR_GROUP_ID')

# ==================== БАЗА ДАННЫХ ====================
def get_db():
    """Получение подключения к БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_vk_message(vk_id, from_user, message_text, is_admin=0):
    """Сохранение сообщения в БД"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO vk_messages (vk_id, from_user, message_text, is_admin)
        VALUES (?, ?, ?, ?)
        ''', (vk_id, from_user, message_text, is_admin))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка сохранения сообщения: {e}")

def get_or_create_client(vk_id, name='VK User'):
    """Получение или создание клиента"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clients WHERE vk_id = ?', (vk_id,))
        client = cursor.fetchone()
        
        if not client:
            cursor.execute('''
            INSERT INTO clients (vk_id, name) VALUES (?, ?)
            ''', (vk_id, name))
            conn.commit()
            client_id = cursor.lastrowid
        else:
            client_id = client['id']
        
        conn.close()
        return client_id
    except Exception as e:
        print(f"❌ Ошибка работы с клиентом: {e}")
        return None

def get_client_cashback(vk_id):
    """Получение баланса кэшбека клиента"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT cashback_balance FROM clients WHERE vk_id = ?', (vk_id,))
        client = cursor.fetchone()
        conn.close()
        return client['cashback_balance'] if client else 0
    except Exception as e:
        print(f"❌ Ошибка получения кэшбека: {e}")
        return 0

def get_price_list():
    """Получение списка услуг"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM price_list')
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    except Exception as e:
        print(f"❌ Ошибка получения прайс-листа: {e}")
        return []

def validate_promo_code(code):
    """Валидация промокода"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT discount_percent, max_uses, current_uses, valid_until, is_active
        FROM promo_codes WHERE code = ?
        ''', (code.upper(),))
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
    except Exception as e:
        print(f"❌ Ошибка валидации промокода: {e}")
        return None

def use_promo_code(code):
    """Использование промокода"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?
        ''', (code.upper(),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка использования промокода: {e}")

def calculate_price(calc_type, params, base_price):
    """Расчёт стоимости по 11 типам"""
    price = 0.0
    
    try:
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
    except Exception as e:
        print(f"❌ Ошибка расчёта цены: {e}")
    
    return round(price, 2)

def apply_discount(total_price, quantity, promo_code=None, cashback_balance=0):
    """Применение скидок и кэшбека"""
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
    
    # Кэшбек (максимум 30% от суммы)
    max_cashback = discounted_price * 0.30
    if cashback_balance > 0:
        cashback_used = min(cashback_balance, max_cashback)
        discounted_price -= cashback_used
    
    return round(discounted_price, 2), int(discount * 100), discount_source, round(cashback_used, 2)

def vk_send_message(vk_id, message):
    """Отправка сообщения ВКонтакте"""
    if not VK_TOKEN or VK_TOKEN == 'YOUR_VK_TOKEN_HERE':
        print(f"[MOCK VK] To {vk_id}: {message}")
        return True
    
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
        result = response.json()
        
        if 'error' in result:
            print(f"❌ VK Error: {result['error']}")
            return False
        
        return result.get('response', {}).get('message_id', 0)
    except requests.exceptions.ReadTimeout:
        print("⚠️ VK ReadTimeout")
        return 0
    except Exception as e:
        print(f"❌ VK Send Error: {e}")
        return 0

def add_cashback(vk_id, order_id, amount):
    """Начисление кэшбека 5% от суммы заказа"""
    try:
        cashback = amount * 0.05
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM clients WHERE vk_id = ?', (vk_id,))
        client = cursor.fetchone()
        
        if client:
            cursor.execute('''
            INSERT INTO cashback_transactions (client_id, order_id, amount, operation_type)
            VALUES (?, ?, ?, 'earned')
            ''', (client['id'], order_id, cashback))
            
            cursor.execute('''
            UPDATE clients SET cashback_balance = cashback_balance + ?, 
                              cashback_earned = cashback_earned + ?
            WHERE vk_id = ?
            ''', (cashback, cashback, vk_id))
            
            conn.commit()
        
        conn.close()
        return cashback
    except Exception as e:
        print(f"❌ Ошибка начисления кэшбека: {e}")
        return 0

# ==================== СОСТОЯНИЕ БОТА ====================
user_states = {}

class VKBotWorker(Thread):
    """VK Bot Worker с LongPoll"""
    
    def __init__(self):
        super().__init__(daemon=True)
        self.last_ts = 0
        self.running = True
        self.reconnect_delay = 5
    
    def run(self):
        """Основной цикл бота"""
        print("🤖 VK Bot запущен в фоновом режиме...")
        print(f"🔑 VK Token: {'✅' if VK_TOKEN and VK_TOKEN != 'YOUR_VK_TOKEN_HERE' else '❌'}")
        
        while self.running:
            try:
                self.poll_messages()
            except requests.exceptions.ReadTimeout:
                print(f"⚠️ ReadTimeout - перезапуск через {self.reconnect_delay}с...")
                time.sleep(self.reconnect_delay)
            except Exception as e:
                print(f"❌ Ошибка бота: {e}")
                time.sleep(self.reconnect_delay)
    
    def poll_messages(self):
        """Получение событий через LongPoll"""
        if not VK_TOKEN or VK_TOKEN == 'YOUR_VK_TOKEN_HERE':
            print("⚠️ VK_TOKEN не настроен. Бот в режиме ожидания...")
            time.sleep(30)
            return
        
        # Получение сервера LongPoll
        url = 'https://api.vk.com/method/messages.getLongPollServer'
        params = {
            'access_token': VK_TOKEN,
            'v': '5.131'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            server_data = response.json().get('response', {})
            
            if not server_data:
                print("❌ Не удалось получить LongPoll сервер")
                time.sleep(5)
                return
            
            longpoll_url = server_data.get('server')
            key = server_data.get('key')
            ts = server_data.get('ts', 0)
            
            print(f"✅ LongPoll подключён: {longpoll_url[:50]}...")
            
            # Цикл опроса
            while self.running:
                try:
                    poll_url = f'{longpoll_url}?act=a_check&key={key}&ts={ts}&wait=25'
                    poll_response = requests.get(poll_url, timeout=30)
                    poll_data = poll_response.json()
                    
                    # Проверка на ошибки LongPoll
                    if 'failed' in poll_data:
                        error_code = poll_data.get('failed')
                        print(f"⚠️ LongPoll error {error_code}, переподключение...")
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
        
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            time.sleep(5)
    
    def handle_message(self, update):
        """Обработка нового сообщения"""
        flags = update[3]
        
        # Игнорирование исходящих сообщений
        if flags & 2:
            return
        
        vk_id = update[3] if isinstance(update[3], int) else update[1]
        message_text = update[6]
        
        # Сохранение сообщения в БД
        save_vk_message(vk_id, vk_id, message_text, is_admin=0)
        
        # Обработка диалога
        self.process_dialog(vk_id, message_text)
    
    def process_dialog(self, vk_id, message_text):
        """Диалоговый автомат с клиентом"""
        state = user_states.get(vk_id, {'step': 'start'})
        step = state.get('step', 'start')
        
        if step == 'start':
            # Показ меню услуг
            price_list = get_price_list()
            cashback = get_client_cashback(vk_id)
            
            menu_text = "🔧 Выберите услугу:\n\n"
            for i, item in enumerate(price_list):
                menu_text += f"{i+1}. {item['name']} - {item['price']}₽\n"
            
            if cashback > 0:
                menu_text += f"\n💰 Ваш кэшбек: {cashback}₽ (можно использовать до 30% от суммы)"
            
            menu_text += "\n\n💡 Есть промокод? Напишите 'PROMO'"
            menu_text += "\n💡 Использовать кэшбек? Напишите 'CASHBACK'"
            menu_text += "\n\nВведите номер услуги:"
            
            vk_send_message(vk_id, menu_text)
            user_states[vk_id] = {'step': 'select_service', 'price_list': price_list}
        
        elif step == 'select_service':
            # Обработка выбора услуги
            if message_text.upper() == 'PROMO':
                vk_send_message(vk_id, "🏷️ Введите ваш промокод:")
                user_states[vk_id]['step'] = 'enter_promo'
                return
            
            if message_text.upper() == 'CASHBACK':
                cashback = get_client_cashback(vk_id)
                vk_send_message(vk_id, f"💰 Ваш баланс кэшбека: {cashback}₽")
                user_states[vk_id]['use_cashback'] = True
                return
            
            try:
                service_idx = int(message_text) - 1
                price_list = state.get('price_list', get_price_list())
                
                if 0 <= service_idx < len(price_list):
                    service = price_list[service_idx]
                    user_states[vk_id] = {
                        'step': 'collect_params',
                        'service': service,
                        'params': {},
                        'promo_code': None,
                        'use_cashback': state.get('use_cashback', False)
                    }
                    self.request_params(vk_id, service)
                else:
                    vk_send_message(vk_id, "❌ Неверный номер. Попробуйте снова:")
            except ValueError:
                vk_send_message(vk_id, "❌ Введите число или 'PROMO'/'CASHBACK':")
        
        elif step == 'enter_promo':
            # Ввод промокода
            promo_code = message_text.upper()
            discount = validate_promo_code(promo_code)
            
            if discount:
                vk_send_message(vk_id, f"✅ Промокод применён! Скидка {int(discount*100)}%")
                user_states[vk_id]['promo_code'] = promo_code
                user_states[vk_id]['step'] = 'select_service'
            else:
                vk_send_message(vk_id, "❌ Промокод недействителен. Попробуйте другой:")
        
        elif step == 'collect_params':
            # Сбор параметров
            service = state.get('service', {})
            params = state.get('params', {})
            calc_type = service.get('calc_type', 'fixed')
            self.collect_param_step(vk_id, message_text, service, params, calc_type)
    
    def request_params(self, vk_id, service):
        """Запрос параметров в зависимости от типа услуги"""
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
        """Пошаговый сбор параметров"""
        current_param = service.get('calc_type', 'fixed')
        
        try:
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
            
            # Расчёт итоговой цены
            base_price = service.get('price', 0)
            total_price = calculate_price(current_param, params, base_price)
            
            quantity = params.get('quantity', 1)
            promo_code = user_states[vk_id].get('promo_code')
            cashback_balance = get_client_cashback(vk_id) if user_states[vk_id].get('use_cashback') else 0
            
            final_price, discount_percent, discount_source, cashback_used = apply_discount(
                total_price, quantity, promo_code, cashback_balance
            )
            
            # Использование промокода
            if promo_code:
                use_promo_code(promo_code)
            
            # Сохранение заказа
            self.save_order(vk_id, service, params, final_price, discount_percent, promo_code, cashback_used)
            
            # Подтверждение
            confirm_text = f"✅ Заказ оформлен!\n"
            confirm_text += f"Услуга: {service['name']}\n"
            confirm_text += f"Сумма: {final_price}₽"
            
            if discount_percent > 0:
                confirm_text += f" (скидка {discount_percent}% via {discount_source})"
            if cashback_used > 0:
                confirm_text += f" (кэшбек: -{cashback_used}₽)"
            
            cashback_earned = final_price * 0.05
            confirm_text += f"\n\n🎁 Вам начислено {cashback_earned:.2f}₽ кэшбека!"
            confirm_text += "\n\nМенеджер свяжется с вами."
            
            vk_send_message(vk_id, confirm_text)
            user_states[vk_id] = {'step': 'start'}
        
        except Exception as e:
            print(f"❌ Ошибка сбора параметров: {e}")
            vk_send_message(vk_id, "❌ Произошла ошибка. Начнём сначала.")
            user_states[vk_id] = {'step': 'start'}
    
    def save_order(self, vk_id, service, params, total_price, discount, promo_code, cashback_used):
        """Сохранение заказа в БД"""
        try:
            client_id = get_or_create_client(vk_id, f"VK User {vk_id}")
            params_text = "; ".join([f"{k}: {v}" for k, v in params.items()])
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO orders (client_id, vk_id, client_name, service_id, service_name,
                               description, parameters, total_price, discount, promo_code,
                               cashback_applied, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client_id, vk_id, f"VK User {vk_id}", service['id'], service['name'],
                service['name'], params_text, total_price, discount, promo_code, cashback_used, 'NEW'
            ))
            
            order_id = cursor.lastrowid
            
            # Начисление кэшбека
            add_cashback(vk_id, order_id, total_price)
            
            conn.commit()
            conn.close()
            
            print(f"✅ Заказ #{order_id} создан для VK {vk_id}")
        
        except Exception as e:
            print(f"❌ Ошибка сохранения заказа: {e}")

# ==================== ЗАПУСК ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 VK Bot Worker для Лазерная Мастерская CRM")
    print("📊 Фаза 3: Склад, Кэшбек, Роли, PWA, AI")
    print("=" * 50)
    
    bot = VKBotWorker()
    bot.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.running = False
        print("\n🛑 Бот остановлен пользователем")