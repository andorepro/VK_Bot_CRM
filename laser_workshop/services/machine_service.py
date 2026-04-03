"""
Сервис управления станками.
Внутренняя логика работы оборудования скрыта от клиентов.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from laser_workshop.core.database.models import Machine, MachineLog, Order


class MachineService:
    """Сервис для управления станками"""

    MAINTENANCE_INTERVAL_HOURS = 100  # ТО каждые 100 часов

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_all_machines(self) -> List[Machine]:
        """Получить все станки"""
        return self.db.query(Machine).all()

    def get_active_machines(self) -> List[Machine]:
        """Получить активные станки"""
        return self.db.query(Machine).filter(Machine.status == 'active').all()

    def get_machine(self, machine_id: int) -> Optional[Machine]:
        """Получить станок по ID"""
        return self.db.query(Machine).get(machine_id)

    def log_job_start(self, machine_id: int, order_id: int, details: str = "") -> MachineLog:
        """Запись начала работы"""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError(f"Станок {machine_id} не найден")

        log = MachineLog(
            machine_id=machine_id,
            event_type='job_start',
            details=f'Заказ #{order_id}. {details}'
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    def log_job_complete(
        self,
        machine_id: int,
        order_id: int,
        duration_minutes: int,
        details: str = ""
    ) -> MachineLog:
        """Запись завершения работы с обновлением наработки"""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError(f"Станок {machine_id} не найден")

        # Обновление наработки
        hours_added = duration_minutes / 60.0
        machine.total_work_hours += hours_added

        # Проверка необходимости ТО
        hours_since_maintenance = machine.total_work_hours
        if machine.last_maintenance:
            # Пересчёт часов после последнего ТО
            pass
        
        if hours_added >= self.MAINTENANCE_INTERVAL_HOURS or \
           (machine.next_maintenance and machine.total_work_hours >= 
            getattr(machine, 'hours_at_last_maintenance', 0) + self.MAINTENANCE_INTERVAL_HOURS):
            machine.status = 'maintenance'
            maintenance_due = machine.total_work_hours - (getattr(machine, 'hours_at_last_maintenance', 0))
            details += f" [Требуется ТО! Наработка: {maintenance_due:.1f}ч]"

        log = MachineLog(
            machine_id=machine_id,
            event_type='job_complete',
            duration_minutes=duration_minutes,
            details=f'Заказ #{order_id}. Длительность: {duration_minutes} мин. {details}'
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    def log_error(self, machine_id: int, error_message: str) -> MachineLog:
        """Запись ошибки"""
        log = MachineLog(
            machine_id=machine_id,
            event_type='error',
            details=error_message
        )
        self.db.add(log)
        
        machine = self.get_machine(machine_id)
        if machine:
            machine.status = 'offline'
        
        self.db.commit()
        self.db.refresh(log)
        return log

    def set_maintenance_complete(self, machine_id: int) -> Machine:
        """Завершение ТО"""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError(f"Станок {machine_id} не найден")

        machine.status = 'active'
        machine.last_maintenance = datetime.utcnow()
        machine.next_maintenance = datetime.utcnow() + timedelta(days=30)
        setattr(machine, 'hours_at_last_maintenance', machine.total_work_hours)

        self.db.commit()
        self.db.refresh(machine)

        self.log_event(machine_id, 'maintenance_complete', 'ТО завершено')
        return machine

    def log_event(self, machine_id: int, event_type: str, details: str) -> MachineLog:
        """Запись произвольного события"""
        log = MachineLog(
            machine_id=machine_id,
            event_type=event_type,
            details=details
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_machine_logs(self, machine_id: int, limit: int = 50) -> List[MachineLog]:
        """История событий станка"""
        return self.db.query(MachineLog)\
            .filter(MachineLog.machine_id == machine_id)\
            .order_by(MachineLog.created_at.desc())\
            .limit(limit)\
            .all()

    def get_machines_needing_maintenance(self) -> List[Machine]:
        """Станки, требующие ТО"""
        all_machines = self.get_all_machines()
        needing = []
        
        for m in all_machines:
            hours_since = m.total_work_hours - getattr(m, 'hours_at_last_maintenance', 0)
            if hours_since >= self.MAINTENANCE_INTERVAL_HOURS * 0.9:  # 90% ресурса
                needing.append(m)
        
        return needing

    def get_statistics(self) -> Dict:
        """Статистика по всем станкам"""
        machines = self.get_all_machines()
        
        total_hours = sum(m.total_work_hours for m in machines)
        active_count = len([m for m in machines if m.status == 'active'])
        maintenance_count = len([m for m in machines if m.status == 'maintenance'])
        offline_count = len([m for m in machines if m.status == 'offline'])

        return {
            'total_machines': len(machines),
            'active': active_count,
            'maintenance': maintenance_count,
            'offline': offline_count,
            'total_work_hours': round(total_hours, 2),
            'machines': [
                {
                    'name': m.name,
                    'type': m.type,
                    'status': m.status,
                    'total_hours': round(m.total_work_hours, 2)
                }
                for m in machines
            ]
        }

    def update_status(self, machine_id: int, status: str) -> Machine:
        """Обновление статуса станка"""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError(f"Станок {machine_id} не найден")

        old_status = machine.status
        machine.status = status

        self.db.commit()
        self.db.refresh(machine)

        self.log_event(machine_id, 'status_changed', f'{old_status} -> {status}')
        return machine
