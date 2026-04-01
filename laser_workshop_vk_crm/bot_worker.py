# sys.stdout.reconfigure(encoding='utf-8')
import sys
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

import os
import time
import sqlite3
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
VK_TOKEN = os.getenv('VK_TOKEN', '')
VK_GROUP_ID = os.getenv('VK_GROUP_ID', '')
DB_PATH = os.getenv('DB_PATH', './database.db')

if not VK_TOKEN:
    print("⚠️  VK_TOKEN not set. Bot running in MOCK mode (simulated).")

def get_db():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def vk_request(method, params=None):
    """Make request to VK API with error handling"""
    if not VK_TOKEN:
        return None
    
    url = f"https://api.vk.com/method/{method}"
    params = params or {}
    params['access_token'] = VK_TOKEN
    params['v'] = '5.131'
    
    try:
        r = requests.post(url, data=params, timeout=10)
        response = r.json()
        
        if 'error' in response:
            print(f"❌ VK API Error: {response['error']}")
            return None
            
        return response.get('response')
    
    except requests.exceptions.ReadTimeout:
        print("⚠️  VK ReadTimeout, retrying next cycle...")
        return None
    except requests.exceptions.ConnectionError:
        print("⚠️  VK ConnectionError, check internet...")
        return None
    except Exception as e:
        print(f"❌ VK Request Error: {e}")
        return None

def save_client(vk_id, first_name, last_name):
    """Save or update client in database"""
    conn = get_db()
    conn.execute("""
        INSERT INTO clients (vk_id, first_name, last_name, last_seen) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(vk_id) DO UPDATE SET 
            last_seen=?, 
            first_name=excluded.first_name, 
            last_name=excluded.last_name
    """, (vk_id, first_name, last_name, int(time.time()), int(time.time())))
    conn.close()

def save_message(vk_id, text, is_from_admin=False):
    """Save message to chat history"""
    conn = get_db()
    conn.execute("""
        INSERT INTO chat_messages (vk_id, message_text, is_from_admin, timestamp)
        VALUES (?, ?, ?, ?)
    """, (vk_id, text, 1 if is_from_admin else 0, int(time.time())))
    conn.close()

def create_order(vk_id, calc_type, params, total_price, description_text):
    """Create new order in database"""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO orders (client_vk_id, status, total_price, description, created_at, updated_at)
        VALUES (?, 'NEW', ?, ?, ?, ?)
    """, (vk_id, total_price, description_text, int(time.time()), int(time.time())))
    
    order_id = cursor.lastrowid
    
    # Update client statistics
    conn.execute(
        "UPDATE clients SET total_orders = total_orders + 1, total_spent = total_spent + ? WHERE vk_id = ?", 
        (total_price, vk_id)
    )
    conn.close()
    
    return order_id

def calculate_price_bot(calc_type, params):
    """Duplicate calculation logic for bot (same as app.py)"""
    p = params
    price = 0.0
    
    try:
        if calc_type == 'fixed':
            price = p.get('base_price', 0) * p.get('qty', 1)
        elif calc_type == 'area_cm2':
            area = (p.get('length', 0) / 10.0) * (p.get('width', 0) / 10.0)
            price = area * p.get('base_price', 0) * p.get('qty', 1)
        elif calc_type == 'meter_thickness':
            meters = p.get('length', 0) / 1000.0
            factor = p.get('thickness', 3.0) / 3.0
            price = meters * (p.get('base_price', 0) * factor) * p.get('qty', 1)
        elif calc_type == 'per_minute':
            price = p.get('minutes', 0) * p.get('base_price', 0)
        elif calc_type == 'per_char':
            price = p.get('chars', 0) * p.get('base_price', 0) * p.get('qty', 1)
        elif calc_type == 'vector_length':
            meters = p.get('length', 0) / 1000.0
            price = meters * p.get('base_price', 0)
        elif calc_type == 'setup_batch':
            setup = p.get('base_price', 0)
            unit_price = p.get('unit_price', 0)
            qty = p.get('qty', 1)
            discount = 0
            if qty >= 100: discount = 0.20
            elif qty >= 50: discount = 0.15
            elif qty >= 20: discount = 0.10
            elif qty >= 10: discount = 0.05
            price = setup + (unit_price * qty * (1 - discount))
        elif calc_type == 'photo_raster':
            area = (p.get('length', 0) / 10.0) * (p.get('width', 0) / 10.0)
            dpi_mult = 1.5 if p.get('dpi', 300) > 600 else 1.0
            price = area * p.get('base_price', 0) * dpi_mult
        elif calc_type == 'cylindrical':
            area = (p.get('diameter', 0) * 3.14 * p.get('length', 0)) / 100.0
            price = area * p.get('base_price', 0)
        elif calc_type == 'volume_3d':
            vol = (p.get('length', 0)/10.0) * (p.get('width', 0)/10.0) * p.get('depth', 0)
            price = vol * p.get('base_price', 0)
        elif calc_type == 'material_and_cut':
            mat_area = (p.get('length', 0)/10.0) * (p.get('width', 0)/10.0)
            cut_len = p.get('cut_length', 0) / 1000.0
            price = (mat_area * p.get('material_price', 0)) + (cut_len * p.get('cut_price', 0))
    except Exception as e:
        print(f"❌ Bot calculation error: {e}")
        return 0.0
    
    return round(price, 2)

def start_bot():
    """Main bot loop with LongPoll"""
    print("🤖 VK Bot worker starting...")
    
    # In-memory session storage for conversation state
    # Key: vk_id, Value: {'step': str, 'data': dict}
    user_sessions = {} 
    
    last_ts = 0
    server_data = None
    
    while True:
        try:
            # If no token, run in mock mode
            if not VK_TOKEN:
                time.sleep(10)
                continue
            
            # Get LongPoll server info if needed
            if server_data is None:
                server_data = vk_request('groups.getLongPollServer', {'group_id': VK_GROUP_ID})
                if not server_data:
                    time.sleep(5)
                    continue
                last_ts = server_data['ts']
            
            # Get events
            events = vk_request('groups.getLongPollEvents', {
                'server': server_data['server'],
                'ts': last_ts,
                'wait': 20,
                'act': 'a_check'
            })
            
            if events and 'updates' in events:
                last_ts = events['ts']
                
                for event in events['updates']:
                    if event['type'] == 'message_new':
                        obj = event['object']
                        msg_text = obj.get('text', '').strip()
                        user_id = obj['peer_id']
                        
                        # Ignore messages from chats or groups
                        if user_id < 0:
                            continue
                        
                        # Get user info
                        user_info = vk_request('users.get', {'user_ids': user_id})
                        if user_info:
                            u = user_info[0]
                            save_client(user_id, u.get('first_name', ''), u.get('last_name', ''))
                        
                        # Save incoming message
                        save_message(user_id, msg_text, is_from_admin=False)
                        
                        # Get or create session
                        session = user_sessions.get(user_id, {'step': 'start', 'data': {}})
                        
                        # State machine for conversation
                        if session['step'] == 'start':
                            # Show menu
                            conn = get_db()
                            services = conn.execute("SELECT name, calc_type, base_price FROM price_list").fetchall()
                            conn.close()
                            
                            menu = "👋 Привет! Выберите услугу:\n\n"
                            for i, s in enumerate(services, 1):
                                menu += f"{i}. {s['name']} ({s['base_price']}₽)\n"
                            menu += "\nОтправьте номер услуги:"
                            
                            vk_request('messages.send', {
                                'peer_id': user_id, 
                                'message': menu, 
                                'random_id': int(time.time())
                            })
                            
                            session['step'] = 'select_service'
                            session['data'] = {
                                'services': {str(i): {'calc_type': s['calc_type'], 'base_price': s['base_price']} 
                                           for i, s in enumerate(services, 1)}
                            }
                            user_sessions[user_id] = session
                        
                        elif session['step'] == 'select_service':
                            if msg_text in session['data']['services']:
                                service = session['data']['services'][msg_text]
                                session['data']['calc_type'] = service['calc_type']
                                session['data']['base_price'] = service['base_price']
                                session['step'] = 'input_params'
                                session['data']['params'] = {}
                                
                                # Ask for parameters based on calc_type
                                ct = service['calc_type']
                                prompts = {
                                    'fixed': "Введите количество штук:",
                                    'per_minute': "Введите примерное время в минутах:",
                                    'per_char': "Введите количество символов:",
                                    'area_cm2': "Введите длину и ширину в мм (например: 100 50):",
                                    'meter_thickness': "Введите длину реза в мм и толщину материала (например: 500 3):",
                                    'vector_length': "Введите длину вектора в мм:",
                                    'cylindrical': "Введите диаметр и длину в мм (например: 70 200):",
                                    'volume_3d': "Введите длину, ширину и глубину в мм (например: 50 30 5):",
                                    'photo_raster': "Введите длину и ширину в мм (например: 100 150):",
                                    'setup_batch': "Введите цену за штуку и количество (например: 150 50):",
                                    'material_and_cut': "Введите длину, ширину в мм, длину реза в мм, цену материала за см² и цену реза за метр (например: 200 150 300 2 10):"
                                }
                                
                                prompt = prompts.get(ct, "Введите параметры:")
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': prompt, 
                                    'random_id': int(time.time())
                                })
                                user_sessions[user_id] = session
                            else:
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': "❌ Неверный номер. Выберите из списка:", 
                                    'random_id': int(time.time())
                                })
                        
                        elif session['step'] == 'input_params':
                            try:
                                vals = [float(x) for x in msg_text.split()]
                                p = session['data']['params']
                                p['base_price'] = session['data']['base_price']
                                ct = session['data']['calc_type']
                                
                                # Parse parameters based on type
                                if ct == 'fixed':
                                    p['qty'] = int(vals[0])
                                elif ct == 'per_minute':
                                    p['minutes'] = vals[0]
                                elif ct == 'per_char':
                                    p['chars'] = int(vals[0])
                                elif ct == 'area_cm2':
                                    p['length'] = vals[0]
                                    p['width'] = vals[1] if len(vals) > 1 else vals[0]
                                    p['qty'] = 1
                                elif ct == 'meter_thickness':
                                    p['length'] = vals[0]
                                    p['thickness'] = vals[1] if len(vals) > 1 else 3.0
                                    p['qty'] = 1
                                elif ct == 'vector_length':
                                    p['length'] = vals[0]
                                elif ct == 'cylindrical':
                                    p['diameter'] = vals[0]
                                    p['length'] = vals[1] if len(vals) > 1 else 100
                                elif ct == 'volume_3d':
                                    p['length'] = vals[0]
                                    p['width'] = vals[1] if len(vals) > 1 else vals[0]
                                    p['depth'] = vals[2] if len(vals) > 2 else 1.0
                                elif ct == 'photo_raster':
                                    p['length'] = vals[0]
                                    p['width'] = vals[1] if len(vals) > 1 else vals[0]
                                    p['dpi'] = 300
                                elif ct == 'setup_batch':
                                    p['unit_price'] = vals[0]
                                    p['qty'] = int(vals[1]) if len(vals) > 1 else 1
                                elif ct == 'material_and_cut':
                                    p['length'] = vals[0]
                                    p['width'] = vals[1] if len(vals) > 1 else vals[0]
                                    p['cut_length'] = vals[2] if len(vals) > 2 else 0
                                    p['material_price'] = vals[3] if len(vals) > 3 else 1.0
                                    p['cut_price'] = vals[4] if len(vals) > 4 else 5.0
                                
                                # Calculate price
                                estimated_price = calculate_price_bot(ct, p)
                                
                                # Create description (flat text)
                                desc_parts = [f"Услуга: {ct}"]
                                for k, v in p.items():
                                    desc_parts.append(f"{k}: {v}")
                                description = ", ".join(desc_parts)
                                
                                msg = f"💰 Ориентировочная цена: {estimated_price}₽\n\n"
                                msg += f"Параметры: {description}\n\n"
                                msg += "Подтвердить заказ? (Да/Нет)"
                                
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': msg, 
                                    'random_id': int(time.time())
                                })
                                
                                session['step'] = 'confirm'
                                session['data']['price'] = estimated_price
                                session['data']['description'] = description
                                user_sessions[user_id] = session
                                
                            except Exception as e:
                                print(f"❌ Parse error: {e}")
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': "❌ Ошибка формата. Попробуйте снова.", 
                                    'random_id': int(time.time())
                                })
                        
                        elif session['step'] == 'confirm':
                            if msg_text.lower() in ['да', 'yes', '+', 'подтверждаю']:
                                order_id = create_order(
                                    user_id,
                                    session['data']['calc_type'],
                                    session['data']['params'],
                                    session['data']['price'],
                                    session['data']['description']
                                )
                                
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': f"✅ Заказ #{order_id} создан!\nМенеджер скоро свяжется с вами.", 
                                    'random_id': int(time.time())
                                })
                                print(f"✅ Order #{order_id} created for user {user_id}")
                                
                                session['step'] = 'start'
                                session['data'] = {}
                            else:
                                vk_request('messages.send', {
                                    'peer_id': user_id, 
                                    'message': "❌ Заказ отменен.\nНачнем сначала? (отправьте любой текст)", 
                                    'random_id': int(time.time())
                                })
                                session['step'] = 'start'
                                session['data'] = {}
                            
                            user_sessions[user_id] = session
            
            else:
                # No events, update ts if available
                if events:
                    last_ts = events.get('ts', last_ts)
            
            # Small delay to prevent CPU spinning
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Bot Loop Error: {e}")
            server_data = None  # Reset server data to reconnect
            time.sleep(5)

if __name__ == '__main__':
    start_bot()
