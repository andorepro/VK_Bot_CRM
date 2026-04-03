"""
Сервис управления заказами
"""
from datetime import datetime
from core.models.database import get_db_connection
from core.services.calculator import Calculator
from core.config import CASHBACK_PERCENT

class OrderService:
    """Сервис для работы с заказами"""
    
    @staticmethod
    def create_order(client_id, service_id, parameters, quantity=1, priority='normal', promo_code=None):
        """
        Создание нового заказа с автоматическим расчётом стоимости
        
        :param client_id: ID клиента
        :param service_id: ID услуги
        :param parameters: параметры заказа (JSON строка или dict)
        :param quantity: количество
        :param priority: приоритет (normal, urgent, deferred)
        :param promo_code: промокод
        :return: dict с информацией о заказе
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем информацию об услуге
        cursor.execute('SELECT * FROM services WHERE id = ?', (service_id,))
        service = cursor.fetchone()
        
        if not service:
            conn.close()
            raise ValueError("Услуга не найдена")
        
        # Расчёт стоимости
        calc_type = service['calc_type']
        base_price = service['base_price']
        
        params = {
            'base_price': base_price,
            'quantity': quantity
        }
        
        # Добавляем параметры из запроса
        if isinstance(parameters, str):
            import json
            try:
                params.update(json.loads(parameters))
            except:
                pass
        elif isinstance(parameters, dict):
            params.update(parameters)
        
        # Вычисляем стоимость
        unit_price = Calculator.calculate(calc_type, params)
        total_price = unit_price * quantity
        
        # Применяем оптовую скидку
        discount = 0
        if quantity >= 10:
            discount = Calculator.apply_bulk_discount(unit_price, quantity)
            total_price = discount * quantity
        
        # Применяем промокод
        final_price = total_price
        if promo_code:
            cursor.execute('SELECT * FROM promo_codes WHERE code = ? AND is_active = 1', (promo_code,))
            promo = cursor.fetchone()
            if promo and promo['current_uses'] < promo['max_uses']:
                final_price = Calculator.apply_promo_code(total_price, promo)
                # Увеличиваем счётчик использований
                cursor.execute(
                    'UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?',
                    (promo_code,)
                )
        
        # Определяем станок на основе типа услуги
        machine_assigned = OrderService._assign_machine(service['name'])
        
        # Создаём заказ
        cursor.execute('''
            INSERT INTO orders (
                client_id, service_id, status, priority, parameters,
                quantity, unit_price, total_price, discount, final_price,
                machine_assigned, created_at, updated_at
            ) VALUES (?, ?, 'new', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (
            client_id, service_id, priority,
            str(parameters) if isinstance(parameters, dict) else parameters,
            quantity, unit_price, total_price, 
            total_price - final_price, final_price,
            machine_assigned
        ))
        
        order_id = cursor.lastrowid
        
        # Обновляем статистику клиента
        cursor.execute('''
            UPDATE clients 
            SET total_orders = total_orders + 1,
                total_spent = total_spent + final_price
            WHERE id = ?
        ''', (client_id,))
        
        conn.commit()
        conn.close()
        
        return {
            'order_id': order_id,
            'client_id': client_id,
            'service_name': service['name'],
            'total_price': total_price,
            'discount': total_price - final_price,
            'final_price': final_price,
            'machine_assigned': machine_assigned,
            'status': 'new'
        }
    
    @staticmethod
    def _assign_machine(service_name):
        """
        Автоматическое назначение станка на основе услуги
        Скрыто от клиентов, используется только внутри системы
        """
        service_lower = service_name.lower()
        
        # JPT M7 60W для металлов
        if any(keyword in service_lower for keyword in ['металл', 'steel', 'metal', 'jpt']):
            return 'jpt_m7_60w'
        
        # Ortur LM3 10W для неметаллов
        if any(keyword in service_lower for keyword in ['дерево', 'кожа', 'фанер', 'акрил', 'пластик', 'wood', 'leather']):
            return 'ortur_lm3_10w'
        
        # По умолчанию Ortur
        return 'ortur_lm3_10w'
    
    @staticmethod
    def update_status(order_id, new_status, comment='', changed_by='admin'):
        """
        Обновление статуса заказа с записью в историю
        
        :param order_id: ID заказа
        :param new_status: новый статус
        :param comment: комментарий
        :param changed_by: кто изменил
        :return: bool
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем текущий статус
        cursor.execute('SELECT status, client_id FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            conn.close()
            return False
        
        old_status = order['status']
        
        # Обновляем статус
        cursor.execute('''
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_status, order_id))
        
        # Если заказ завершён, начисляем кэшбек
        if new_status == 'done' and old_status != 'done':
            cursor.execute('SELECT final_price FROM orders WHERE id = ?', (order_id,))
            order_data = cursor.fetchone()
            cashback = order_data['final_price'] * (CASHBACK_PERCENT / 100)
            
            cursor.execute('''
                UPDATE clients 
                SET cashback_balance = cashback_balance + ?
                WHERE id = ?
            ''', (cashback, order['client_id']))
            
            cursor.execute('''
                UPDATE orders 
                SET completed_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (order_id,))
            
            # Записываем в журнал станка
            cursor.execute('''
                SELECT machine_assigned FROM orders WHERE id = ?
            ''', (order_id,))
            machine = cursor.fetchone()
            if machine and machine['machine_assigned']:
                cursor.execute('''
                    INSERT INTO machine_logs (machine_id, event_type, order_id, details)
                    VALUES (?, 'job_complete', ?, ?)
                ''', (machine['machine_assigned'], order_id, f'Заказ #{order_id} завершён'))
        
        # Записываем в историю
        cursor.execute('''
            INSERT INTO order_history (order_id, old_status, new_status, comment, changed_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, old_status, new_status, comment, changed_by))
        
        conn.commit()
        conn.close()
        
        return True
    
    @staticmethod
    def get_orders(status=None, client_id=None, search_query=None, limit=50):
        """
        Получение списка заказов с фильтрацией
        
        :param status: фильтр по статусу
        :param client_id: фильтр по клиенту
        :param search_query: поисковый запрос
        :param limit: лимит записей
        :return: list of dict
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT o.*, c.name as client_name, s.name as service_name
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            JOIN services s ON o.service_id = s.id
            WHERE 1=1
        '''
        
        params = []
        
        if status:
            query += ' AND o.status = ?'
            params.append(status)
        
        if client_id:
            query += ' AND o.client_id = ?'
            params.append(client_id)
        
        if search_query:
            query += ' AND (o.description LIKE ? OR c.name LIKE ? OR o.id LIKE ?)'
            search_param = f'%{search_query}%'
            params.extend([search_param, search_param, search_param])
        
        query += ' ORDER BY o.created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_order_by_id(order_id):
        """Получение заказа по ID"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT o.*, c.name as client_name, c.vk_id, s.name as service_name, s.calc_type
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            JOIN services s ON o.service_id = s.id
            WHERE o.id = ?
        ''', (order_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def get_order_history(order_id):
        """Получение истории изменений заказа"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM order_history 
            WHERE order_id = ? 
            ORDER BY changed_at DESC
        ''', (order_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
