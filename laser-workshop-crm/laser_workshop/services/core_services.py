# -*- coding: utf-8 -*-
"""
Сервисы приложения
Уведомления, платежи, аналитика, бэкапы
"""

import os
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис уведомлений"""
    
    def __init__(self, vk_api=None):
        self.vk_api = vk_api
    
    def send_vk_message(self, user_id: int, message: str, keyboard=None):
        """Отправка сообщения ВКонтакте"""
        if not self.vk_api:
            logger.warning('VK API не инициализирован')
            return False
        
        try:
            params = {
                'peer_id': user_id,
                'message': message,
                'random_id': 0
            }
            if keyboard:
                params['keyboard'] = keyboard
            
            self.vk_api.messages.send(**params)
            logger.info(f'Сообщение отправлено пользователю {user_id}')
            return True
        except Exception as e:
            logger.error(f'Ошибка отправки VK сообщения: {e}')
            return False
    
    def send_order_notification(self, user_id: int, order_number: str, status: str):
        """Уведомление о статусе заказа"""
        status_emoji = {
            'new': '🆕',
            'in_progress': '⚙️',
            'awaiting_payment': '💰',
            'ready': '✅',
            'completed': '🎉',
            'cancelled': '❌'
        }
        
        emoji = status_emoji.get(status, '📦')
        message = f'{emoji} Статус заказа #{order_number} изменён\nСтатус: {status}'
        
        return self.send_vk_message(user_id, message)
    
    def send_broadcast(self, user_ids: List[int], message: str):
        """Массовая рассылка"""
        success_count = 0
        for user_id in user_ids:
            if self.send_vk_message(user_id, message):
                success_count += 1
        
        logger.info(f'Рассылка завершена: {success_count}/{len(user_ids)}')
        return success_count


class PaymentService:
    """Сервис платежей"""
    
    def __init__(self, yookassa_secret=None, cdek_api_key=None):
        self.yookassa_secret = yookassa_secret
        self.cdek_api_key = cdek_api_key
    
    def create_payment(self, order_id: int, amount: float, description: str):
        """Создание платежа (заглушка)"""
        # TODO: Интеграция с ЮKassa
        logger.info(f'Платёж для заказа {order_id}: {amount} руб.')
        return {'payment_id': f'pay_{order_id}', 'status': 'pending'}
    
    def verify_payment(self, payment_id: str):
        """Проверка статуса платежа"""
        # TODO: Интеграция с ЮKassa
        return {'status': 'succeeded'}
    
    def calculate_delivery(self, address: str, weight: float):
        """Расчёт стоимости доставки CDEK"""
        # TODO: Интеграция с CDEK API
        return {'cost': 500, 'days': 3}


class AnalyticsService:
    """Сервис аналитики"""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
    
    def get_daily_stats(self, date=None):
        """Статистика за день"""
        if date is None:
            date = datetime.now().date()
        
        # TODO: Запрос к БД
        return {
            'date': str(date),
            'orders_count': 0,
            'revenue': 0,
            'new_clients': 0
        }
    
    def get_monthly_report(self, year: int, month: int):
        """Отчёт за месяц"""
        # TODO: Запрос к БД
        return {
            'year': year,
            'month': month,
            'total_orders': 0,
            'total_revenue': 0,
            'top_services': [],
            'top_materials': []
        }
    
    def get_client_analytics(self, client_id: int):
        """Аналитика по клиенту"""
        return {
            'total_orders': 0,
            'total_spent': 0,
            'cashback': 0,
            'last_order_date': None
        }


class BackupService:
    """Сервис резервного копирования"""
    
    def __init__(self, backup_dir: str):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self, db_path: str) -> str:
        """Создание резервной копии БД"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'workshop_backup_{timestamp}.db'
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        try:
            import shutil
            shutil.copy2(db_path, backup_path)
            logger.info(f'Бэкап создан: {backup_path}')
            
            # Удаляем старые бэкапы (храним последние 7 дней)
            self.cleanup_old_backups(days=7)
            
            return backup_path
        except Exception as e:
            logger.error(f'Ошибка создания бэкапа: {e}')
            return None
    
    def cleanup_old_backups(self, days: int = 7):
        """Удаление старых бэкапов"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(self.backup_dir):
            if filename.startswith('workshop_backup_'):
                filepath = os.path.join(self.backup_dir, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_mtime < cutoff_date:
                    os.remove(filepath)
                    logger.info(f'Удалён старый бэкап: {filename}')


# Глобальные экземпляры сервисов
notification_service = None
payment_service = None
analytics_service = None
backup_service = None


def init_services(settings):
    """Инициализация сервисов"""
    global notification_service, payment_service, analytics_service, backup_service
    
    notification_service = NotificationService()
    payment_service = PaymentService(settings.YOOKASSA_SECRET, settings.CDEK_API_KEY)
    analytics_service = AnalyticsService()
    backup_service = BackupService(settings.BACKUP_DIR)
    
    logger.info('Сервисы инициализированы')
