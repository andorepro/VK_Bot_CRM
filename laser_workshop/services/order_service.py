"""
Сервис управления заказами.
Автоматическое распределение станков скрыто от клиентов.
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from laser_workshop.core.database.models import Order, Service, Machine, Client, Material, OrderLog, MachineLog, CashbackTransaction


class OrderService:
    """Сервис для управления заказами"""

    CASHBACK_PERCENT = 5.0  # 5% кэшбек

    def __init__(self, db_session: Session):
        self.db = db_session

    def create_order(
        self,
        client_id: int,
        service_id: int,
        area_cm2: float,
        quantity: int = 1,
        material_id: Optional[int] = None,
        description: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Order:
        """Создание нового заказа с авторасчётом стоимости"""
        
        service = self.db.query(Service).get(service_id)
        if not service:
            raise ValueError(f"Услуга с ID {service_id} не найдена")

        material = None
        price_modifier = 1.0
        if material_id:
            material = self.db.query(Material).get(material_id)
            if material:
                price_modifier = material.price_modifier

        # Расчёт стоимости
        base_cost = service.base_price_per_cm2 * area_cm2 * quantity * price_modifier
        total_amount = max(base_cost, service.min_order_price)

        # Автоматический выбор станка (скрыто от клиента)
        assigned_machine = self._auto_assign_machine(service)

        order = Order(
            client_id=client_id,
            service_id=service_id,
            material_id=material_id,
            area_cm2=area_cm2,
            quantity=quantity,
            description=description,
            file_path=file_path,
            assigned_machine_id=assigned_machine.id if assigned_machine else None,
            total_amount=total_amount,
            cashback_amount=round(total_amount * self.CASHBACK_PERCENT / 100, 2),
            status='new'
        )

        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        # Логирование
        self._log_order_action(order, 'created', f'Стоимость: {total_amount} руб. Станок: {assigned_machine.name if assigned_machine else "Не назначен"}')

        return order

    def _auto_assign_machine(self, service: Service) -> Optional[Machine]:
        """Автоматический выбор подходящего станка на основе типа услуги"""
        compatible_types = service.compatible_machine_types.split(';') if service.compatible_machine_types else []
        
        machine = self.db.query(Machine).filter(
            and_(
                Machine.type.in_(compatible_types),
                Machine.status == 'active'
            )
        ).order_by(Machine.total_work_hours).first()

        return machine

    def assign_to_machine(self, order_id: int, machine_id: int) -> Order:
        """Ручное назначение станка (для админки)"""
        order = self.db.query(Order).get(order_id)
        if not order:
            raise ValueError(f"Заказ {order_id} не найден")

        machine = self.db.query(Machine).get(machine_id)
        if not machine:
            raise ValueError(f"Станок {machine_id} не найден")

        order.assigned_machine_id = machine_id
        self.db.commit()
        self.db.refresh(order)

        self._log_order_action(order, 'machine_assigned', f'Назначен станок: {machine.name}')
        return order

    def update_status(self, order_id: int, status: str) -> Order:
        """Обновление статуса заказа"""
        order = self.db.query(Order).get(order_id)
        if not order:
            raise ValueError(f"Заказ {order_id} не найден")

        old_status = order.status
        order.status = status
        
        if status == 'completed':
            order.completed_at = datetime.utcnow()
            self._accrue_cashback(order)

        self.db.commit()
        self.db.refresh(order)

        self._log_order_action(order, 'status_changed', f'{old_status} -> {status}')
        return order

    def _accrue_cashback(self, order: Order):
        """Начисление кэшбека клиенту"""
        client = self.db.query(Client).get(order.client_id)
        if client and order.cashback_amount > 0:
            client.cashback_balance += order.cashback_amount
            client.total_spent += order.total_amount

            transaction = CashbackTransaction(
                client_id=client.id,
                order_id=order.id,
                amount=order.cashback_amount,
                transaction_type='accrual'
            )
            self.db.add(transaction)

    def get_order(self, order_id: int) -> Optional[Order]:
        """Получение заказа по ID"""
        return self.db.query(Order).get(order_id)

    def get_client_orders(self, client_id: int, limit: int = 10) -> List[Order]:
        """История заказов клиента"""
        return self.db.query(Order)\
            .filter(Order.client_id == client_id)\
            .order_by(Order.created_at.desc())\
            .limit(limit)\
            .all()

    def get_active_orders(self) -> List[Order]:
        """Активные заказы (не завершённые и не отменённые)"""
        return self.db.query(Order)\
            .filter(~Order.status.in_(['completed', 'cancelled']))\
            .order_by(Order.created_at)\
            .all()

    def _log_order_action(self, order: Order, action: str, details: str):
        """Логирование действий с заказом"""
        log = OrderLog(
            order_id=order.id,
            action=action,
            details=details
        )
        self.db.add(log)
        self.db.commit()

    def calculate_price(
        self,
        service_id: int,
        area_cm2: float,
        quantity: int = 1,
        material_id: Optional[int] = None
    ) -> Dict:
        """Расчёт стоимости без создания заказа"""
        service = self.db.query(Service).get(service_id)
        if not service:
            return {'error': 'Услуга не найдена'}

        material = None
        modifier_name = "Без материала"
        price_modifier = 1.0
        
        if material_id:
            material = self.db.query(Material).get(material_id)
            if material:
                price_modifier = material.price_modifier
                modifier_name = material.name

        base_cost = service.base_price_per_cm2 * area_cm2 * quantity * price_modifier
        total_amount = max(base_cost, service.min_order_price)
        cashback = round(total_amount * self.CASHBACK_PERCENT / 100, 2)

        return {
            'service_name': service.name,
            'material': modifier_name,
            'area_cm2': area_cm2,
            'quantity': quantity,
            'base_cost': round(base_cost, 2),
            'min_order_price': service.min_order_price,
            'total_amount': round(total_amount, 2),
            'cashback': cashback,
            'final_price': round(total_amount, 2)
        }
