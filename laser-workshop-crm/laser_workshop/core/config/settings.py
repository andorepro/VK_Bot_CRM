# -*- coding: utf-8 -*-
"""
Конфигурация приложения
Загрузка переменных окружения и настройка параметров
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загрузка .env файла
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Settings:
    """Настройки приложения"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'laser_workshop_secret_key_2026_change_this')
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    USE_HTTPS = os.getenv('USE_HTTPS', 'True').lower() == 'true'
    
    # База данных
    DB_PATH = os.getenv('DB_PATH', os.path.join(BASE_DIR, 'workshop.db'))
    
    # VK Bot
    VK_TOKEN = os.getenv('VK_TOKEN', '')
    VK_GROUP_ID = os.getenv('VK_GROUP_ID', '')
    ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []
    
    # Платежи
    YOOKASSA_SECRET = os.getenv('YOOKASSA_SECRET', '')
    CDEK_API_KEY = os.getenv('CDEK_API_KEY', '')
    
    # Администратор по умолчанию
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    
    # Директории
    BACKUP_DIR = os.getenv('BACKUP_DIR', os.path.join(BASE_DIR, 'backups'))
    CERTS_DIR = os.getenv('CERTS_DIR', os.path.join(BASE_DIR, 'certs'))
    LOGS_DIR = os.getenv('LOGS_DIR', os.path.join(BASE_DIR, 'logs'))
    STATIC_DIR = os.getenv('STATIC_DIR', os.path.join(BASE_DIR, 'static'))
    TEMPLATE_DIR = os.getenv('TEMPLATE_DIR', os.path.join(BASE_DIR, 'templates'))
    
    @classmethod
    def create_dirs(cls):
        """Создание необходимых директорий"""
        for directory in [cls.BACKUP_DIR, cls.CERTS_DIR, cls.LOGS_DIR, cls.STATIC_DIR, cls.TEMPLATE_DIR]:
            os.makedirs(directory, exist_ok=True)


def get_settings():
    """Получение настроек"""
    return Settings()
