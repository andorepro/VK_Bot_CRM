#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VK Bot for Laser Workshop CRM with Real Database Integration
Features:
- Separate menus for Admin and Client
- Persistent inline keyboards
- Real SQLite DB integration (Orders, Users, Cashback, Stock)
- Dialog state management
- Long Poll API support
"""

import os
import sys
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# Load environment variables
load_dotenv()

# Configuration
VK_TOKEN = os.getenv('VK_TOKEN')
DB_PATH = os.getenv('DB_PATH', 'workshop.db')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('VK_Bot')

# In-memory state storage (for production use Redis)
user_states = {}

class DatabaseManager:
    """Manager for SQLite database operations"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables if they don't exist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'client',
                cashback REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                vk_id INTEGER NOT NULL,
                service_type TEXT,
                material_type TEXT,
                thickness REAL,
                area REAL,
                quantity INTEGER DEFAULT 1,
                price REAL,
                discount REAL DEFAULT 0.0,
                final_price REAL,
                status TEXT DEFAULT 'new',
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vk_id) REFERENCES users(vk_id)
            )
        ''')
        
        # Stock table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_name TEXT UNIQUE NOT NULL,
                material_type TEXT,
                thickness REAL,
                size_x REAL,
                size_y REAL,
                quantity INTEGER DEFAULT 0,
                unit TEXT,
                min_quantity INTEGER DEFAULT 5,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Cashback transactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cashback_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER NOT NULL,
                amount REAL,
                transaction_type TEXT,
                order_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vk_id) REFERENCES users(vk_id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings
        default_settings = [
            ('cashback_percent', '5'),
            ('admin_notification', 'true'),
            ('auto_confirm', 'false')
        ]
        for key, value in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def get_or_create_user(self, vk_id, name=None):
        """Get existing user or create new one"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE vk_id = ?', (vk_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute('''
                INSERT INTO users (vk_id, name, role) 
                VALUES (?, ?, ?)
            ''', (vk_id, name, 'client'))
            conn.commit()
            cursor.execute('SELECT * FROM users WHERE vk_id = ?', (vk_id,))
            user = cursor.fetchone()
            logger.info(f"New user created: VK ID {vk_id}")
        else:
            # Update last visit
            cursor.execute('''
                UPDATE users SET last_visit = CURRENT_TIMESTAMP WHERE vk_id = ?
            ''', (vk_id,))
            conn.commit()
        
        conn.close()
        return dict(user) if user else None
    
    def get_user_role(self, vk_id):
        """Get user role from database"""
        if vk_id in ADMIN_IDS:
            return 'admin'
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM users WHERE vk_id = ?', (vk_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result['role'] if result else 'client'
    
    def create_order(self, vk_id, order_data):
        """Create new order in database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{vk_id}"
        
        cursor.execute('''
            INSERT INTO orders (
                order_number, vk_id, service_type, material_type, 
                thickness, area, quantity, price, discount, 
                final_price, status, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_number, vk_id, order_data.get('service_type'),
            order_data.get('material_type'), order_data.get('thickness'),
            order_data.get('area'), order_data.get('quantity', 1),
            order_data.get('price', 0), order_data.get('discount', 0),
            order_data.get('final_price', 0), 'new',
            order_data.get('comment', '')
        ))
        
        conn.commit()
        
        # Get created order
        cursor.execute('SELECT * FROM orders WHERE order_number = ?', (order_number,))
        order = dict(cursor.fetchone()) if cursor.fetchone() else None
        
        conn.close()
        
        if order:
            logger.info(f"Order created: {order_number}")
            self.add_cashback_transaction(vk_id, order['final_price'] * 0.05, 'accrual', order['id'], f"Кэшбек за заказ {order_number}")
        
        return order
    
    def get_orders_by_status(self, status=None, limit=10):
        """Get orders by status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT o.*, u.name as user_name 
                FROM orders o 
                JOIN users u ON o.vk_id = u.vk_id 
                WHERE o.status = ? 
                ORDER BY o.created_at DESC 
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT o.*, u.name as user_name 
                FROM orders o 
                JOIN users u ON o.vk_id = u.vk_id 
                ORDER BY o.created_at DESC 
                LIMIT ?
            ''', (limit,))
        
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders
    
    def update_order_status(self, order_id, status):
        """Update order status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (status, order_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Order {order_id} status updated to {status}")
    
    def get_user_orders(self, vk_id, limit=10):
        """Get user's orders"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM orders 
            WHERE vk_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (vk_id, limit))
        
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders
    
    def get_user_cashback(self, vk_id):
        """Get user's cashback balance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT cashback FROM users WHERE vk_id = ?', (vk_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result['cashback'] if result else 0.0
    
    def add_cashback_transaction(self, vk_id, amount, transaction_type, order_id=None, description=None):
        """Add cashback transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Add transaction
        cursor.execute('''
            INSERT INTO cashback_transactions (vk_id, amount, transaction_type, order_id, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (vk_id, amount, transaction_type, order_id, description))
        
        # Update user cashback
        if transaction_type == 'accrual':
            cursor.execute('''
                UPDATE users SET cashback = cashback + ? WHERE vk_id = ?
            ''', (amount, vk_id))
        elif transaction_type == 'usage':
            cursor.execute('''
                UPDATE users SET cashback = cashback - ? WHERE vk_id = ?
            ''', (amount, vk_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Cashback transaction: {amount} for VK {vk_id}")
    
    def get_stock_items(self, low_stock_only=False):
        """Get stock items"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if low_stock_only:
            cursor.execute('''
                SELECT * FROM stock 
                WHERE quantity <= min_quantity 
                ORDER BY quantity ASC
            ''')
        else:
            cursor.execute('SELECT * FROM stock ORDER BY material_name')
        
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    
    def get_statistics(self, days=30):
        """Get statistics for the last N days"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        date_from = datetime.now() - timedelta(days=days)
        
        # Total orders
        cursor.execute('''
            SELECT COUNT(*) as count, SUM(final_price) as revenue
            FROM orders 
            WHERE created_at >= ?
        ''', (date_from,))
        stats = dict(cursor.fetchone())
        
        # Orders by status
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM orders 
            WHERE created_at >= ?
            GROUP BY status
        ''', (date_from,))
        status_stats = {row['status']: row['count'] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_orders': stats['count'] or 0,
            'revenue': stats['revenue'] or 0.0,
            'by_status': status_stats
        }

# Initialize database manager
db = DatabaseManager(DB_PATH)

class VKBot:
    """VK Bot class with Long Poll support"""
    
    def __init__(self, token):
        self.token = token
        self.vk = vk_api.VkApi(token=token)
        self.longpoll = VkLongPoll(self.vk)
        logger.info("VK Bot initialized")
    
    def send_message(self, user_id, text, keyboard=None, attachment=None):
        """Send message to user"""
        try:
            params = {
                'peer_id': user_id,
                'message': text,
                'random_id': get_random_id()
            }
            
            if keyboard:
                params['keyboard'] = keyboard.get_keyboard()
            
            if attachment:
                params['attachment'] = attachment
            
            self.vk.method('messages.send', params)
            logger.debug(f"Message sent to {user_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    def get_main_keyboard(self, role):
        """Get main menu keyboard based on role"""
        keyboard = VkKeyboard(one_time=False, inline=False)
        
        if role == 'admin':
            # Admin menu
            keyboard.add_button('📊 Все заказы', color=VkKeyboardColor.PRIMARY)
            keyboard.add_row()
            keyboard.add_button('✅ Подтвердить заказ', color=VkKeyboardColor.POSITIVE)
            keyboard.add_row()
            keyboard.add_button('📦 Склад', color=VkKeyboardColor.SECONDARY)
            keyboard.add_row()
            keyboard.add_button('📈 Статистика', color=VkKeyboardColor.PRIMARY)
            keyboard.add_row()
            keyboard.add_button('📢 Рассылка', color=VkKeyboardColor.SECONDARY)
            keyboard.add_row()
            keyboard.add_button('⚙️ Настройки', color=VkKeyboardColor.NEGATIVE)
        else:
            # Client menu
            keyboard.add_button('📝 Новый заказ', color=VkKeyboardColor.POSITIVE)
            keyboard.add_row()
            keyboard.add_button('📦 Мои заказы', color=VkKeyboardColor.PRIMARY)
            keyboard.add_row()
            keyboard.add_button('💰 Мой кэшбек', color=VkKeyboardColor.SECONDARY)
            keyboard.add_row()
            keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
        
        return keyboard
    
    def get_cancel_keyboard(self):
        """Get cancel button keyboard"""
        keyboard = VkKeyboard(one_time=False, inline=False)
        keyboard.add_button('❌ Отмена', color=VkKeyboardColor.NEGATIVE)
        return keyboard
    
    def get_confirmation_keyboard(self, yes_callback=None, no_callback=None):
        """Get Yes/No confirmation keyboard"""
        keyboard = VkKeyboard(one_time=False, inline=False)
        keyboard.add_button('✅ Да', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('❌ Нет', color=VkKeyboardColor.NEGATIVE)
        return keyboard
    
    def handle_start_command(self, user_id, first_name):
        """Handle /start command"""
        user = db.get_or_create_user(user_id, first_name)
        role = db.get_user_role(user_id)
        
        greeting = f"Привет, {first_name}! 👋\n\n"
        if role == 'admin':
            greeting += "Вы авторизованы как АДМИНИСТРАТОР.\nДоступны все функции управления."
        else:
            greeting += "Добро пожаловать в лазерную мастерскую!\nВыберите действие в меню."
        
        keyboard = self.get_main_keyboard(role)
        self.send_message(user_id, greeting, keyboard)
    
    def handle_new_order(self, user_id):
        """Start new order dialog"""
        user_states[user_id] = {'step': 'service_type'}
        
        keyboard = VkKeyboard(one_time=False, inline=False)
        services = [
            'Гравировка', 'Резка дерева', 'Резка акрила', 
            'Резка фанеры', 'Маркировка', '3D гравировка'
        ]
        
        for i, service in enumerate(services):
            keyboard.add_button(service, color=VkKeyboardColor.PRIMARY)
            if (i + 1) % 2 == 0:
                keyboard.add_row()
        
        keyboard.add_row()
        keyboard.add_button('❌ Отмена', color=VkKeyboardColor.NEGATIVE)
        
        self.send_message(
            user_id,
            "📝 Выберите тип услуги:\n" + "\n".join([f"{i+1}. {s}" for i, s in enumerate(services)]),
            keyboard
        )
    
    def handle_my_orders(self, user_id):
        """Show user's orders"""
        orders = db.get_user_orders(user_id, limit=5)
        
        if not orders:
            self.send_message(user_id, "У вас пока нет заказов.", self.get_main_keyboard('client'))
            return
        
        message = "📦 Ваши последние заказы:\n\n"
        for order in orders:
            status_emoji = {'new': '🆕', 'in_progress': '⚙️', 'completed': '✅', 'cancelled': '❌'}.get(order['status'], '📄')
            message += f"{status_emoji} Заказ #{order['order_number']}\n"
            message += f"   Услуга: {order['service_type']}\n"
            message += f"   Цена: {order['final_price']} ₽\n"
            message += f"   Статус: {order['status']}\n\n"
        
        keyboard = self.get_main_keyboard('client')
        self.send_message(user_id, message, keyboard)
    
    def handle_cashback(self, user_id):
        """Show user's cashback"""
        cashback = db.get_user_cashback(user_id)
        
        message = f"💰 Ваш кэшбек: {cashback:.2f} ₽\n\n"
        message += "Кэшбек начисляется с каждого заказа (5%)\n"
        message += "Можно использовать при оплате следующих заказов."
        
        keyboard = self.get_main_keyboard('client')
        self.send_message(user_id, message, keyboard)
    
    def handle_help(self, user_id):
        """Show help information"""
        message = """ℹ️ Помощь

📝 Как сделать заказ:
1. Нажмите "Новый заказ"
2. Выберите услугу
3. Укажите параметры
4. Подтвердите заказ

📦 Статусы заказов:
🆕 - Новый
⚙️ - В работе
✅ - Готов
❌ - Отменён

💰 Кэшбек:
5% от суммы заказа возвращается на ваш счёт

📞 Контакты:
Телефон: +7 (999) 000-00-00
Адрес: ул. Примерная, 1
"""
        keyboard = self.get_main_keyboard('client')
        self.send_message(user_id, message, keyboard)
    
    def handle_admin_all_orders(self, user_id):
        """Show all orders for admin"""
        orders = db.get_orders_by_status(limit=10)
        
        if not orders:
            self.send_message(user_id, "Заказов пока нет.", self.get_main_keyboard('admin'))
            return
        
        message = "📊 Все заказы (последние 10):\n\n"
        for order in orders:
            status_emoji = {'new': '🆕', 'in_progress': '⚙️', 'completed': '✅', 'cancelled': '❌'}.get(order['status'], '📄')
            message += f"{status_emoji} #{order['order_number']} - {order['user_name'] or 'Аноним'}\n"
            message += f"   {order['service_type']} | {order['final_price']} ₽ | {order['status']}\n\n"
        
        keyboard = self.get_main_keyboard('admin')
        self.send_message(user_id, message, keyboard)
    
    def handle_admin_stock(self, user_id):
        """Show stock information"""
        items = db.get_stock_items()
        
        if not items:
            self.send_message(user_id, "Склад пуст.", self.get_main_keyboard('admin'))
            return
        
        message = "📦 Склад материалов:\n\n"
        for item in items:
            warning = " ⚠️ МАЛО" if item['quantity'] <= item['min_quantity'] else ""
            message += f"{item['material_name']} ({item['thickness']}мм): {item['quantity']} {item['unit']}{warning}\n"
        
        keyboard = self.get_main_keyboard('admin')
        self.send_message(user_id, message, keyboard)
    
    def handle_admin_statistics(self, user_id):
        """Show statistics"""
        stats = db.get_statistics(days=30)
        
        message = f"""📈 Статистика за 30 дней:

Всего заказов: {stats['total_orders']}
Выручка: {stats['revenue']:.2f} ₽

По статусам:
"""
        for status, count in stats['by_status'].items():
            message += f"  {status}: {count}\n"
        
        keyboard = self.get_main_keyboard('admin')
        self.send_message(user_id, message, keyboard)
    
    def process_order_step(self, user_id, text):
        """Process order creation step by step"""
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        step = state.get('step')
        
        if step == 'service_type':
            state['service_type'] = text
            state['step'] = 'material_type'
            
            keyboard = VkKeyboard(one_time=False, inline=False)
            materials = ['Фанера', 'Акрил', 'Дерево', 'Плексиглас', 'Кожа', 'Ткань']
            for mat in materials:
                keyboard.add_button(mat, color=VkKeyboardColor.PRIMARY)
                keyboard.add_row()
            keyboard.add_button('❌ Отмена', color=VkKeyboardColor.NEGATIVE)
            
            self.send_message(user_id, f"✅ Выбрано: {text}\n\nВыберите материал:", keyboard)
        
        elif step == 'material_type':
            state['material_type'] = text
            state['step'] = 'thickness'
            
            keyboard = self.get_cancel_keyboard()
            self.send_message(user_id, f"✅ Материал: {text}\n\nУкажите толщину в мм (числом):", keyboard)
        
        elif step == 'thickness':
            try:
                thickness = float(text.replace(',', '.'))
                state['thickness'] = thickness
                state['step'] = 'size'
                
                keyboard = self.get_cancel_keyboard()
                self.send_message(user_id, f"✅ Толщина: {thickness}мм\n\nУкажите размеры в мм (формат: 100x100):", keyboard)
            except ValueError:
                self.send_message(user_id, "❌ Ошибка: введите число (например, 3 или 3.5)", self.get_cancel_keyboard())
        
        elif step == 'size':
            try:
                parts = text.lower().replace(' ', '').split('x')
                if len(parts) != 2:
                    raise ValueError()
                width, height = float(parts[0]), float(parts[1])
                area = (width * height) / 1000000  # m²
                state['area'] = area
                state['size'] = f"{width}x{height}"
                state['step'] = 'quantity'
                
                keyboard = self.get_cancel_keyboard()
                self.send_message(user_id, f"✅ Размер: {width}x{height}мм (площадь: {area:.4f} м²)\n\nУкажите количество (шт):", keyboard)
            except (ValueError, IndexError):
                self.send_message(user_id, "❌ Ошибка: формат 100x100", self.get_cancel_keyboard())
        
        elif step == 'quantity':
            try:
                quantity = int(text)
                state['quantity'] = quantity
                
                # Calculate price (simplified)
                base_price = 1000  # rub per m²
                price = round(state['area'] * base_price * quantity * 1.5)
                state['price'] = price
                state['final_price'] = price
                state['step'] = 'confirm'
                
                keyboard = self.get_confirmation_keyboard()
                message = f"""✅ Параметры заказа:
Услуга: {state['service_type']}
Материал: {state['material_type']}
Толщина: {state['thickness']}мм
Размер: {state['size']}мм
Количество: {quantity} шт
Площадь: {state['area']:.4f} м²

💰 Стоимость: {price} ₽

Подтверждаете заказ?"""
                self.send_message(user_id, message, keyboard)
            except ValueError:
                self.send_message(user_id, "❌ Ошибка: введите целое число", self.get_cancel_keyboard())
    
    def handle_events(self):
        """Main event loop for Long Poll"""
        logger.info("Starting Long Poll event loop...")
        
        for event in self.longpoll.listen():
            try:
                if event.type == VkEventType.MESSAGE_NEW:
                    user_id = event.user_id
                    text = event.text.lower().strip()
                    
                    # Get user info
                    user = db.get_or_create_user(user_id)
                    role = db.get_user_role(user_id)
                    first_name = user.get('name', 'Пользователь')
                    
                    # Check if user is in dialog state
                    if user_id in user_states:
                        state = user_states[user_id]
                        
                        # Handle cancel
                        if text == 'отмена' or text == '❌ отмена':
                            del user_states[user_id]
                            self.send_message(
                                user_id, 
                                "❌ Заказ отменён.", 
                                self.get_main_keyboard(role)
                            )
                            continue
                        
                        # Handle confirmation
                        if state.get('step') == 'confirm':
                            if text in ['да', '✅ да']:
                                order = db.create_order(user_id, state)
                                del user_states[user_id]
                                
                                message = f"""✅ Заказ создан!
Номер: {order['order_number']}
Сумма: {order['final_price']} ₽
Статус: {order['status']}

Вам начислено {order['final_price'] * 0.05:.2f} ₽ кэшбека."""
                                self.send_message(user_id, message, self.get_main_keyboard(role))
                                
                                # Notify admins
                                for admin_id in ADMIN_IDS:
                                    if admin_id != user_id:
                                        self.send_message(
                                            admin_id,
                                            f"🔔 Новый заказ #{order['order_number']} от {first_name}\nСумма: {order['final_price']} ₽",
                                            self.get_main_keyboard('admin')
                                        )
                            else:
                                del user_states[user_id]
                                self.send_message(user_id, "❌ Заказ отменён.", self.get_main_keyboard(role))
                            continue
                        
                        # Process order steps
                        self.process_order_step(user_id, event.text)
                        continue
                    
                    # Main menu commands
                    if text in ['/start', 'начать', 'привет']:
                        self.handle_start_command(user_id, first_name)
                    
                    elif text == '📝 новый заказ':
                        self.handle_new_order(user_id)
                    
                    elif text == '📦 мои заказы':
                        self.handle_my_orders(user_id)
                    
                    elif text == '💰 мой кэшбек':
                        self.handle_cashback(user_id)
                    
                    elif text == 'ℹ️ помощь':
                        self.handle_help(user_id)
                    
                    # Admin commands
                    elif role == 'admin':
                        if text == '📊 все заказы':
                            self.handle_admin_all_orders(user_id)
                        elif text == '✅ подтвердить заказ':
                            self.send_message(user_id, "Введите номер заказа для подтверждения:", self.get_cancel_keyboard())
                            user_states[user_id] = {'step': 'admin_confirm_order'}
                        elif text == '📦 склад':
                            self.handle_admin_stock(user_id)
                        elif text == '📈 статистика':
                            self.handle_admin_statistics(user_id)
                        elif text == '📢 рассылка':
                            self.send_message(user_id, "Введите текст рассылки:", self.get_cancel_keyboard())
                            user_states[user_id] = {'step': 'admin_broadcast'}
                        elif text == '⚙️ настройки':
                            self.send_message(user_id, "⚙️ Настройки в разработке", self.get_main_keyboard('admin'))
                    
                    # Admin special states
                    elif user_id in user_states:
                        state = user_states[user_id]
                        if state.get('step') == 'admin_confirm_order':
                            # Simplified: just mark as confirmed
                            self.send_message(user_id, f"✅ Заказ {event.text} подтверждён (демо режим)", self.get_main_keyboard('admin'))
                            del user_states[user_id]
                        elif state.get('step') == 'admin_broadcast':
                            # Send broadcast to all clients
                            conn = db.get_connection()
                            cursor = conn.cursor()
                            cursor.execute('SELECT vk_id FROM users WHERE role = ?', ('client',))
                            clients = cursor.fetchall()
                            conn.close()
                            
                            count = 0
                            for client in clients:
                                try:
                                    self.send_message(client[0], f"📢 Важное сообщение:\n\n{event.text}")
                                    count += 1
                                except:
                                    pass
                            
                            self.send_message(user_id, f"✅ Рассылка отправлена {count} клиентам", self.get_main_keyboard('admin'))
                            del user_states[user_id]
            
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

def main():
    """Main function"""
    if not VK_TOKEN:
        logger.error("VK_TOKEN not found in environment variables!")
        sys.exit(1)
    
    bot = VKBot(VK_TOKEN)
    
    try:
        bot.handle_events()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
