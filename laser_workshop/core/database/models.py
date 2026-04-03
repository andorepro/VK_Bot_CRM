"""
Модели базы данных для CRM системы лазерной мастерской.
Скрытая логика распределения станков не видна клиентам.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Machine(Base):
    """Станки (внутренний ресурс, не виден клиентам)"""
    __tablename__ = 'machines'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # JPT M7 60W, Ortur LM3 10W
    type = Column(String(50), nullable=False)   # fiber_marker, diode_engraver
    status = Column(String(20), default='active')  # active, maintenance, offline
    total_work_hours = Column(Float, default=0.0)
    last_maintenance = Column(DateTime, nullable=True)
    next_maintenance = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="machine")
    logs = relationship("MachineLog", back_populates="machine", cascade="all, delete-orphan")


class Service(Base):
    """Услуги прайс-листа"""
    __tablename__ = 'services'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    base_price_per_cm2 = Column(Float, default=0.0)  # Цена за см²
    min_order_price = Column(Float, default=300.0)   # Минимальная стоимость заказа
    compatible_machine_types = Column(String(200))   # fiber_marker;diode_engraver
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Material(Base):
    """Материалы для гравировки/резки"""
    __tablename__ = 'materials'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))  # metal, wood, leather, plastic, glass
    max_thickness_mm = Column(Float)
    price_modifier = Column(Float, default=1.0)  # Коэффициент к цене
    is_active = Column(Boolean, default=True)


class Client(Base):
    """Клиенты"""
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True)
    name = Column(String(100))
    phone = Column(String(20))
    balance = Column(Float, default=0.0)
    cashback_balance = Column(Float, default=0.0)
    total_spent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="client")


class Order(Base):
    """Заказы клиентов"""
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    service_id = Column(Integer, ForeignKey('services.id'), nullable=False)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=True)
    
    # Параметры заказа
    area_cm2 = Column(Float, default=0.0)
    quantity = Column(Integer, default=1)
    description = Column(Text)
    file_path = Column(String(255))
    
    # Внутренняя логика (скрыто от клиента)
    assigned_machine_id = Column(Integer, ForeignKey('machines.id'))
    cost_price = Column(Float, default=0.0)
    
    # Финансы
    total_amount = Column(Float, default=0.0)
    cashback_amount = Column(Float, default=0.0)
    is_paid = Column(Boolean, default=False)
    
    # Статусы
    status = Column(String(50), default='new')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    client = relationship("Client", back_populates="orders")
    service = relationship("Service")
    material = relationship("Material")
    machine = relationship("Machine", back_populates="orders")
    logs = relationship("OrderLog", back_populates="order", cascade="all, delete-orphan")

    Index('idx_client_status', 'client_id', 'status')


class OrderLog(Base):
    """История изменений заказов"""
    __tablename__ = 'order_logs'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    action = Column(String(50))
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="logs")


class MachineLog(Base):
    """Журнал работы станков"""
    __tablename__ = 'machine_logs'

    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey('machines.id'), nullable=False)
    event_type = Column(String(50))
    duration_minutes = Column(Integer, default=0)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    machine = relationship("Machine", back_populates="logs")


class Stock(Base):
    """Склад материалов"""
    __tablename__ = 'stock'

    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id'))
    quantity = Column(Float, default=0.0)
    unit = Column(String(20))
    min_level = Column(Float, default=10.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material = relationship("Material")


class CashbackTransaction(Base):
    """Транзакции кэшбека"""
    __tablename__ = 'cashback_transactions'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    amount = Column(Float)
    transaction_type = Column(String(20))  # accrual, redemption
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client")
    order = relationship("Order")


class Setting(Base):
    """Настройки системы"""
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
