# -*- coding: utf-8 -*-
"""
Сервис управления лазерными станками
Поддержка: JPT M7 60W (оптоволоконный маркер) и Ortur LM3 10W (диодный гравёр)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MachineType(Enum):
    """Типы лазерных станков"""
    FIBER_MARKER = 'fiber_marker'  # Оптоволоконный маркер (JPT M7)
    DIODE_ENGRAVER = 'diode_engraver'  # Диодный гравёр (Ortur LM3)
    CO2_LASER = 'co2_laser'  # CO2 лазер


class MachineStatus(Enum):
    """Статусы станка"""
    OFFLINE = 'offline'
    IDLE = 'idle'
    WORKING = 'working'
    PAUSED = 'paused'
    ERROR = 'error'
    MAINTENANCE = 'maintenance'


class LaserMachineService:
    """Сервис управления лазерными станками"""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.machines_cache: Dict[int, dict] = {}
    
    def get_all_machines(self, active_only: bool = False) -> List[dict]:
        """Получение списка всех станков"""
        if not self.db:
            return []
        
        cursor = self.db.cursor()
        query = 'SELECT * FROM machines'
        if active_only:
            query += ' WHERE is_active = 1'
        query += ' ORDER BY id'
        
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_machine_by_id(self, machine_id: int) -> Optional[dict]:
        """Получение информации о станке по ID"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM machines WHERE id = ?', (machine_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_machine_by_type(self, machine_type: MachineType) -> Optional[dict]:
        """Получение первого доступного станка указанного типа"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT * FROM machines 
            WHERE machine_type = ? AND is_active = 1 AND status IN ('idle', 'offline')
            ORDER BY total_work_hours ASC
            LIMIT 1
        ''', (machine_type.value,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_machine_status(self, machine_id: int, status: MachineStatus, 
                             job_id: Optional[int] = None) -> bool:
        """Обновление статуса станка"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            cursor.execute('''
                UPDATE machines 
                SET status = ?, current_job_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status.value, job_id, machine_id))
            self.db.commit()
            
            logger.info(f'Станок {machine_id}: статус изменён на {status.value}')
            return True
        except Exception as e:
            logger.error(f'Ошибка обновления статуса станка: {e}')
            return False
    
    def log_machine_event(self, machine_id: int, event_type: str, 
                         message: str = '', duration_seconds: int = 0,
                         temperature: float = None, power_percent: float = None,
                         speed_percent: float = None, error_code: str = None,
                         operator_id: int = None, order_id: int = None) -> int:
        """Логирование события станка"""
        if not self.db:
            return -1
        
        try:
            cursor = self.db.cursor()
            cursor.execute('''
                INSERT INTO machine_logs 
                (machine_id, event_type, message, duration_seconds, temperature,
                 power_percent, speed_percent, error_code, operator_id, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (machine_id, event_type, message, duration_seconds, temperature,
                  power_percent, speed_percent, error_code, operator_id, order_id))
            
            log_id = cursor.lastrowid
            self.db.commit()
            
            logger.debug(f'Событие {event_type} записано в журнал (ID: {log_id})')
            return log_id
        except Exception as e:
            logger.error(f'Ошибка логирования события: {e}')
            return -1
    
    def start_job(self, machine_id: int, order_id: int, operator_id: int = None) -> bool:
        """Запуск работы над заказом"""
        if not self.update_machine_status(machine_id, MachineStatus.WORKING, order_id):
            return False
        
        self.log_machine_event(
            machine_id=machine_id,
            event_type='job_start',
            message=f'Начало работы над заказом #{order_id}',
            operator_id=operator_id,
            order_id=order_id
        )
        
        return True
    
    def complete_job(self, machine_id: int, order_id: int, 
                    work_time_minutes: int, operator_id: int = None) -> bool:
        """Завершение работы над заказом"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            
            # Обновление статистики станка
            cursor.execute('''
                UPDATE machines 
                SET status = 'idle', 
                    current_job_id = NULL,
                    total_work_hours = total_work_hours + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (work_time_minutes / 60.0, machine_id))
            
            # Логирование завершения
            self.log_machine_event(
                machine_id=machine_id,
                event_type='job_complete',
                message=f'Завершение работы над заказом #{order_id}',
                duration_seconds=work_time_minutes * 60,
                operator_id=operator_id,
                order_id=order_id
            )
            
            self.db.commit()
            logger.info(f'Заказ #{order_id} завершён на станке {machine_id}')
            return True
        except Exception as e:
            logger.error(f'Ошибка завершения работы: {e}')
            return False
    
    def get_machine_statistics(self, machine_id: int, days: int = 30) -> dict:
        """Получение статистики работы станка"""
        if not self.db:
            return {}
        
        cursor = self.db.cursor()
        since_date = datetime.now() - timedelta(days=days)
        
        # Общая статистика
        cursor.execute('''
            SELECT 
                COUNT(*) as total_jobs,
                SUM(duration_seconds) as total_work_seconds,
                AVG(duration_seconds) as avg_job_duration
            FROM machine_logs
            WHERE machine_id = ? 
              AND event_type = 'job_complete'
              AND created_at >= ?
        ''', (machine_id, since_date.isoformat()))
        
        stats_row = cursor.fetchone()
        
        # Статусы ошибок
        cursor.execute('''
            SELECT error_code, COUNT(*) as count
            FROM machine_logs
            WHERE machine_id = ? 
              AND event_type = 'error'
              AND created_at >= ?
            GROUP BY error_code
            ORDER BY count DESC
        ''', (machine_id, since_date.isoformat()))
        
        errors = [dict(row) for row in cursor.fetchall()]
        
        return {
            'machine_id': machine_id,
            'period_days': days,
            'total_jobs': stats_row['total_jobs'] or 0,
            'total_work_hours': (stats_row['total_work_seconds'] or 0) / 3600,
            'avg_job_duration_minutes': (stats_row['avg_job_duration'] or 0) / 60,
            'errors': errors
        }
    
    def recommend_machine_for_order(self, service_type: str, 
                                    material_type: str = None,
                                    thickness: float = None) -> Optional[dict]:
        """Рекомендация станка для заказа на основе типа услуги и материала"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        
        # Поиск услуги для получения рекомендуемого станка
        cursor.execute('''
            SELECT recommended_machine_id, max_material_thickness
            FROM services
            WHERE code = ? OR name LIKE ?
            LIMIT 1
        ''', (service_type, f'%{service_type}%'))
        
        service_row = cursor.fetchone()
        
        if service_row and service_row['recommended_machine_id']:
            # Проверка совместимости по толщине материала
            if thickness and service_row['max_material_thickness']:
                if thickness > service_row['max_material_thickness']:
                    logger.warning(f'Толщина материала {thickness}мм превышает максимальную для этой услуги')
            
            machine = self.get_machine_by_id(service_row['recommended_machine_id'])
            if machine and machine['is_active'] and machine['status'] in ('idle', 'offline'):
                return machine
        
        # Если рекомендуемый станок недоступен, ищем альтернативу
        if service_type in ('engrave_metal', 'mark_metal', 'engrave_anodized'):
            # Для металла нужен оптоволоконный лазер JPT M7
            return self.get_machine_by_type(MachineType.FIBER_MARKER)
        elif service_type in ('engrave_wood', 'cut_plywood', 'engrave_leather', 
                             'engrave_plastic', 'engrave_glass'):
            # Для неметаллов подходит диодный лазер Ortur LM3
            return self.get_machine_by_type(MachineType.DIODE_ENGRAVER)
        
        # Возвращаем любой свободный станок
        cursor.execute('''
            SELECT * FROM machines 
            WHERE is_active = 1 AND status IN ('idle', 'offline')
            ORDER BY total_work_hours ASC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def schedule_maintenance(self, machine_id: int, maintenance_date: datetime,
                            notes: str = '') -> bool:
        """Планирование технического обслуживания"""
        if not self.db:
            return False
        
        try:
            cursor = self.db.cursor()
            cursor.execute('''
                UPDATE machines 
                SET next_maintenance = ?, 
                    status = 'maintenance',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (maintenance_date.date().isoformat(), machine_id))
            
            self.log_machine_event(
                machine_id=machine_id,
                event_type='maintenance_scheduled',
                message=f'ТО запланировано на {maintenance_date}. {notes}'
            )
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f'Ошибка планирования ТО: {e}')
            return False
    
    def get_maintenance_due_machines(self) -> List[dict]:
        """Получение станков, требующих ТО"""
        if not self.db:
            return []
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT *, 
                   julianday(next_maintenance) - julianday('now') as days_until_due
            FROM machines
            WHERE is_active = 1 
              AND next_maintenance IS NOT NULL
              AND julianday(next_maintenance) - julianday('now') <= 7
            ORDER BY days_until_due ASC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def calculate_work_time_estimate(self, area_cm2: float, complexity: str = 'standard',
                                    machine_id: int = None) -> int:
        """
        Расчёт предполагаемого времени работы в минутах
        area_cm2: площадь гравировки/резки в см²
        complexity: сложность (simple, standard, complex)
        """
        # Базовая скорость в см²/минуту в зависимости от типа станка
        base_speed = {
            'fiber_marker': 15.0,    # JPT M7 - быстро для маркировки
            'diode_engraver': 5.0,   # Ortur LM3 - медленнее
            'co2_laser': 10.0
        }
        
        # Коэффициенты сложности
        complexity_factors = {
            'simple': 1.0,
            'standard': 1.5,
            'complex': 2.5,
            'ultra': 4.0
        }
        
        machine = self.get_machine_by_id(machine_id) if machine_id else None
        machine_type = machine['machine_type'] if machine else 'diode_engraver'
        
        speed = base_speed.get(machine_type, 5.0)
        factor = complexity_factors.get(complexity, 1.5)
        
        estimated_minutes = (area_cm2 / speed) * factor
        
        # Добавляем время на установку/настройку (5-15 минут)
        setup_time = 5 if area_cm2 < 50 else 10 if area_cm2 < 200 else 15
        
        return int(estimated_minutes + setup_time)


# Глобальный экземпляр сервиса
machine_service = None


def init_machine_service(db_connection):
    """Инициализация сервиса станков"""
    global machine_service
    machine_service = LaserMachineService(db_connection)
    logger.info('Сервис управления станками инициализирован')
    return machine_service
