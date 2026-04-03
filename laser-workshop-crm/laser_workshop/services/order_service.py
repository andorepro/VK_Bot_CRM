# -*- coding: utf-8 -*-
"""
Сервис управления заказами для CRM лазерной мастерской
Расчёт стоимости, управление статусами, назначение на станки
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OrderStatus:
    """Статусы заказа"""
    NEW = 'new'                      # Новый заказ
    CONFIRMED = 'confirmed'          # Подтверждён клиентом
    IN_PROGRESS = 'in_progress'      # В работе
    AWAITING_PAYMENT = 'awaiting_payment'  # Ожидает оплаты
    PAID = 'paid'                    # Оплачен
    READY = 'ready'                  # Готов к выдаче
    COMPLETED = 'completed'          # Завершён
    CANCELLED = 'cancelled'          # Отменён
    REFUNDED = 'refunded'            # Возврат средств


class Priority:
    """Приоритеты заказа"""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'


class OrderService:
    """Сервис управления заказами"""
    
    def __init__(self, db_connection=None, machine_service=None):
        self.db = db_connection
        self.machine_service = machine_service
    
    def create_order(self, client_id: int, service_type: str,
                    material_type: str = None, material_thickness: float = None,
                    width_mm: float = None, height_mm: float = None,
                    quantity: int = 1, complexity: str = 'standard',
                    comment: str = None, deadline: datetime = None,
                    priority: str = 'normal') -> Optional[int]:
        """Создание нового заказа"""
        if not self.db:
            return None
        
        try:
            cursor = self.db.cursor()
            
            # Генерация номера заказа
            order_number = self._generate_order_number(cursor)
            
            # Расчёт площади
            area_cm2 = None
            if width_mm and height_mm:
                area_cm2 = (width_mm * height_mm * quantity) / 100.0
            
            # Получение расценок
            base_price, setup_price = self._get_service_pricing(service_type)
            
            # Расчёт стоимости
            price_material = 0.0
            price_work = 0.0
            price_setup = setup_price if setup_price else 0.0
            
            if area_cm2 and base_price:
                price_work = area_cm2 * base_price
            
            # Получение материала для расчёта стоимости
            if material_type:
                material_price = self._get_material_price(material_type, material_thickness)
                if material_price:
                    price_material = material_price * quantity
            
            # Итоговая стоимость
            subtotal = price_material + price_work + price_setup
            
            # Проверка минимальной стоимости заказа
            min_order_price = self._get_minimum_order_price(service_type)
            if subtotal < min_order_price:
                price_work += (min_order_price - subtotal)
                subtotal = min_order_price
            
            final_price = round(subtotal, 2)
            
            # Определение рекомендуемого станка
            machine_id = None
            if self.machine_service:
                machine = self.machine_service.recommend_machine_for_order(
                    service_type, material_type, material_thickness
                )
                if machine:
                    machine_id = machine['id']
            
            # Расчёт срока выполнения
            if not deadline:
                default_days = self._get_setting('default_deadline_days', 3)
                deadline = datetime.now() + timedelta(days=int(default_days))
            
            # Создание заказа
            cursor.execute('''
                INSERT INTO orders 
                (order_number, client_id, service_type, material_type, 
                 material_thickness, width_mm, height_mm, area_cm2, quantity,
                 complexity_level, machine_id, price_material, price_work, 
                 price_setup, final_price, status, priority, deadline, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_number, client_id, service_type, material_type,
                  material_thickness, width_mm, height_mm, area_cm2, quantity,
                  complexity, machine_id, price_material, price_work,
                  price_setup, final_price, OrderStatus.NEW, priority,
                  deadline.date().isoformat() if deadline else None, comment))
            
            order_id = cursor.lastrowid
            self.db.commit()
            
            logger.info(f'Создан заказ #{order_id} ({order_number}) для клиента {client_id}')
            return order_id
            
        except Exception as e:
            logger.error(f'Ошибка создания заказа: {e}')
            if self.db:
                self.db.rollback()
            return None
    
    def _generate_order_number(self, cursor) -> str:
        """Генерация уникального номера заказа"""
        date_str = datetime.now().strftime('%y%m%d')
        
        cursor.execute('''
            SELECT COUNT(*) FROM orders 
            WHERE order_number LIKE ?
        ''', (f'{date_str}-%',))
        
        count = cursor.fetchone()[0] + 1
        return f'{date_str}-{count:04d}'
    
    def _get_service_pricing(self, service_type: str) -> Tuple[float, float]:
        """Получение базовой цены и стоимости настройки для услуги"""
        if not self.db:
            return 0.0, 150.0
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT base_price_per_cm2, setup_price 
            FROM services 
            WHERE code = ? OR name LIKE ?
            LIMIT 1
        ''', (service_type, f'%{service_type}%'))
        
        row = cursor.fetchone()
        if row:
            return row['base_price_per_cm2'] or 0.0, row['setup_price'] or 150.0
        
        # Цены по умолчанию
        return 2.0, 150.0
    
    def _get_material_price(self, material_type: str, thickness: float = None) -> float:
        """Получение цены материала"""
        if not self.db:
            return 0.0
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT price_per_unit, unit 
            FROM materials 
            WHERE (type = ? OR name LIKE ?) 
              AND (thickness_mm = ? OR ? IS NULL)
              AND is_active = 1
            LIMIT 1
        ''', (material_type, f'%{material_type}%', thickness, thickness))
        
        row = cursor.fetchone()
        return row['price_per_unit'] if row else 0.0
    
    def _get_minimum_order_price(self, service_type: str) -> float:
        """Получение минимальной стоимости заказа"""
        if not self.db:
            return 300.0
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT minimum_order_price 
            FROM services 
            WHERE code = ? OR name LIKE ?
            LIMIT 1
        ''', (service_type, f'%{service_type}%'))
        
        row = cursor.fetchone()
        return row['minimum_order_price'] if row else 300.0
    
    def _get_setting(self, key: str, default: str = '') -> str:
        """Получение настройки из БД"""
        if not self.db:
            return default
        
        cursor = self.db.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    
    def get_order_by_id(self, order_id: int) -> Optional[dict]:
        """Получение заказа по ID"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT o.*, c.name as client_name, c.phone as client_phone,
                   c.vk_id as client_vk_id, m.name as machine_name
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            LEFT JOIN machines m ON o.machine_id = m.id
            WHERE o.id = ?
        ''', (order_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_order_by_number(self, order_number: str) -> Optional[dict]:
        """Получение заказа по номеру"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT o.*, c.name as client_name, c.phone as client_phone,
                   c.vk_id as client_vk_id, m.name as machine_name
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            LEFT JOIN machines m ON o.machine_id = m.id
            WHERE o.order_number = ?
        ''', (order_number,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_order_status(self, order_id: int, status: str,
                           comment: str = None) -> bool:
        """Обновление статуса заказа"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            
            updates = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
            params = [status]
            
            if status == OrderStatus.COMPLETED:
                updates.append('completed_at = CURRENT_TIMESTAMP')
            
            if comment:
                updates.append('comment = ?')
                params.append(comment)
            
            params.append(order_id)
            
            cursor.execute(f'''
                UPDATE orders 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            
            self.db.commit()
            logger.info(f'Заказ #{order_id}: статус изменён на {status}')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка обновления статуса заказа: {e}')
            if self.db:
                self.db.rollback()
            return False
    
    def assign_to_machine(self, order_id: int, machine_id: int,
                         operator_id: int = None) -> bool:
        """Назначение заказа на станок"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            
            # Проверка доступности станка
            if self.machine_service:
                machine = self.machine_service.get_machine_by_id(machine_id)
                if not machine or machine['status'] not in ('idle', 'offline'):
                    logger.warning(f'Станок {machine_id} недоступен')
                    return False
            
            cursor.execute('''
                UPDATE orders 
                SET machine_id = ?, assigned_operator_id = ?,
                    status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (machine_id, operator_id, OrderStatus.IN_PROGRESS, order_id))
            
            # Запуск работы на станке
            if self.machine_service:
                self.machine_service.start_job(machine_id, order_id, operator_id)
            
            self.db.commit()
            logger.info(f'Заказ #{order_id} назначен на станок {machine_id}')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка назначения на станок: {e}')
            if self.db:
                self.db.rollback()
            return False
    
    def complete_order(self, order_id: int, work_time_minutes: int = None,
                      operator_id: int = None) -> bool:
        """Завершение заказа"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            
            order = self.get_order_by_id(order_id)
            if not order:
                return False
            
            # Обновление заказа
            cursor.execute('''
                UPDATE orders 
                SET status = ?, completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (OrderStatus.READY, order_id))
            
            # Завершение работы на станке
            if self.machine_service and order.get('machine_id'):
                actual_work_time = work_time_minutes or order.get('work_time_minutes', 0)
                self.machine_service.complete_job(
                    order['machine_id'], order_id, actual_work_time, operator_id
                )
                
                # Обновление фактического времени работы
                if actual_work_time:
                    cursor.execute('''
                        UPDATE orders SET work_time_minutes = ? WHERE id = ?
                    ''', (actual_work_time, order_id))
            
            self.db.commit()
            logger.info(f'Заказ #{order_id} завершён')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка завершения заказа: {e}')
            if self.db:
                self.db.rollback()
            return False
    
    def get_orders_list(self, status: str = None, client_id: int = None,
                       machine_id: int = None, limit: int = 50,
                       offset: int = 0) -> List[dict]:
        """Получение списка заказов с фильтрацией"""
        if not self.db:
            return []
        
        cursor = self.db.cursor()
        
        query = '''
            SELECT o.*, c.name as client_name, c.phone as client_phone,
                   m.name as machine_name
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            LEFT JOIN machines m ON o.machine_id = m.id
            WHERE 1=1
        '''
        params = []
        
        if status:
            query += ' AND o.status = ?'
            params.append(status)
        
        if client_id:
            query += ' AND o.client_id = ?'
            params.append(client_id)
        
        if machine_id:
            query += ' AND o.machine_id = ?'
            params.append(machine_id)
        
        query += ' ORDER BY o.created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_active_orders(self) -> List[dict]:
        """Получение активных заказов (в работе)"""
        active_statuses = [
            OrderStatus.IN_PROGRESS,
            OrderStatus.AWAITING_PAYMENT,
            OrderStatus.PAID
        ]
        
        if not self.db:
            return []
        
        cursor = self.db.cursor()
        placeholders = ','.join('?' * len(active_statuses))
        
        cursor.execute(f'''
            SELECT o.*, c.name as client_name, m.name as machine_name
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            LEFT JOIN machines m ON o.machine_id = m.id
            WHERE o.status IN ({placeholders})
            ORDER BY 
                CASE o.priority 
                    WHEN 'urgent' THEN 1 
                    WHEN 'high' THEN 2 
                    WHEN 'normal' THEN 3 
                    ELSE 4 
                END,
                o.deadline ASC
        ''', active_statuses)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def calculate_cashback(self, order_id: int) -> float:
        """Расчёт кэшбека для заказа"""
        order = self.get_order_by_id(order_id)
        if not order:
            return 0.0
        
        cashback_percent = float(self._get_setting('cashback_percent', '5'))
        cashback = order['final_price'] * (cashback_percent / 100.0)
        
        # Округление до целых
        return round(cashback)
    
    def apply_cashback(self, client_id: int, order_id: int) -> bool:
        """Начисление кэшбека клиенту"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            
            cashback = self.calculate_cashback(order_id)
            if cashback <= 0:
                return False
            
            # Обновление баланса клиента
            cursor.execute('''
                UPDATE clients 
                SET cashback = cashback + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (cashback, client_id))
            
            # Запись транзакции
            cursor.execute('''
                INSERT INTO cashback_transactions 
                (client_id, order_id, amount, transaction_type, balance_after)
                SELECT ?, ?, ?, 'earn', cashback + ?
                FROM clients WHERE id = ?
            ''', (client_id, order_id, cashback, cashback, client_id))
            
            self.db.commit()
            logger.info(f'Кэшбек {cashback} руб. начислен клиенту {client_id}')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка начисления кэшбека: {e}')
            if self.db:
                self.db.rollback()
            return False
    
    def get_statistics(self, start_date: datetime = None, 
                      end_date: datetime = None) -> dict:
        """Получение статистики по заказам"""
        if not self.db:
            return {}
        
        cursor = self.db.cursor()
        
        # Базовый запрос
        base_query = 'FROM orders WHERE 1=1'
        params = []
        
        if start_date:
            base_query += ' AND created_at >= ?'
            params.append(start_date.isoformat())
        
        if end_date:
            base_query += ' AND created_at <= ?'
            params.append(end_date.isoformat())
        
        # Общая статистика
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_orders,
                SUM(final_price) as total_revenue,
                AVG(final_price) as avg_order_value
            {base_query}
        ''', params)
        
        stats = dict(cursor.fetchone())
        
        # Статистика по статусам
        cursor.execute(f'''
            SELECT status, COUNT(*) as count, SUM(final_price) as revenue
            {base_query}
            GROUP BY status
        ''', params)
        
        stats['by_status'] = {row['status']: {'count': row['count'], 'revenue': row['revenue']} 
                             for row in cursor.fetchall()}
        
        # Популярные услуги
        cursor.execute(f'''
            SELECT service_type, COUNT(*) as count, SUM(final_price) as revenue
            {base_query}
            GROUP BY service_type
            ORDER BY count DESC
            LIMIT 5
        ''', params)
        
        stats['top_services'] = [dict(row) for row in cursor.fetchall()]
        
        return stats


# Глобальный экземпляр сервиса
order_service = None


def init_order_service(db_connection, machine_service=None):
    """Инициализация сервиса заказов"""
    global order_service
    order_service = OrderService(db_connection, machine_service)
    logger.info('Сервис управления заказами инициализирован')
    return order_service
