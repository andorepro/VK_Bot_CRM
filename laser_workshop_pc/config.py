# ==================== МОДУЛЬ КОНФИГУРАЦИИ ====================
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Базовая директория
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    """Класс конфигурации приложения"""

    # Основные настройки
    SECRET_KEY = os.getenv('SECRET_KEY', 'laser_workshop_secret_key_2026_change_this')
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() in ('true', '1', 'yes')
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))

    # HTTPS/SSL настройки
    USE_HTTPS = os.getenv('USE_HTTPS', 'False').lower() in ('true', '1', 'yes')
    CERT_FILE = os.getenv('CERT_FILE', 'certs/server.crt')
    KEY_FILE = os.getenv('KEY_FILE', 'certs/server.key')

    # Полные пути к сертификатам
    if not os.path.isabs(CERT_FILE):
        CERT_FILE = os.path.join(BASE_DIR, CERT_FILE)
    if not os.path.isabs(KEY_FILE):
        KEY_FILE = os.path.join(BASE_DIR, KEY_FILE)

    # База данных
    DB_NAME = os.getenv('DB_NAME', 'workshop.db')
    DB_PATH = os.path.join(BASE_DIR, DB_NAME)
    DB_BACKUP_DIR = os.path.join(BASE_DIR, os.getenv('DB_BACKUP_DIR', 'backups'))

    # Оптимизация производительности
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '10'))
    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', '5'))
    CACHE_SIZE = int(os.getenv('CACHE_SIZE_MB', '64')) * 1024 * 1024

    # Кэширование
    CACHE_TTL = int(os.getenv('CACHE_TTL_SECONDS', '300'))
    MAX_USER_STATES = int(os.getenv('MAX_USER_STATES', '1000'))

    # VK API
    VK_TOKEN = os.getenv('VK_TOKEN', 'YOUR_VK_TOKEN_HERE')
    VK_GROUP_ID = os.getenv('VK_GROUP_ID', 'YOUR_GROUP_ID')

    # Платежные системы
    YOOKASSA_SECRET = os.getenv('YOOKASSA_SECRET', 'YOUR_YOOKASSA_SECRET')
    CDEK_API_KEY = os.getenv('CDEK_API_KEY', 'YOUR_CDEK_API_KEY')

    # AI Прогнозирование
    AI_PROGNOSIS = os.getenv('AI_PROGNOSIS_ENABLED', 'True').lower() in ('true', '1', 'yes')

    # Скидки (пороги и проценты)
    DISCOUNT_TIERS = [
        {'qty': int(os.getenv('DISCOUNT_TIER_1_QTY', '10')), 'percent': int(os.getenv('DISCOUNT_TIER_1_PERCENT', '5'))},
        {'qty': int(os.getenv('DISCOUNT_TIER_2_QTY', '20')), 'percent': int(os.getenv('DISCOUNT_TIER_2_PERCENT', '10'))},
        {'qty': int(os.getenv('DISCOUNT_TIER_3_QTY', '50')), 'percent': int(os.getenv('DISCOUNT_TIER_3_PERCENT', '15'))},
        {'qty': int(os.getenv('DISCOUNT_TIER_4_QTY', '100')), 'percent': int(os.getenv('DISCOUNT_TIER_4_PERCENT', '20'))},
    ]

    # Администратор по умолчанию
    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')

    # JWT Токен
    JWT_EXPIRATION_DAYS = int(os.getenv('JWT_EXPIRATION_DAYS', '7'))

    @classmethod
    def get_discount(cls, quantity):
        """Получение процента скидки в зависимости от количества"""
        discount = 0
        for tier in cls.DISCOUNT_TIERS:
            if quantity >= tier['qty']:
                discount = tier['percent']
        return discount

    @classmethod
    def apply_discount(cls, total_price, quantity):
        """Применение скидки к общей сумме"""
        discount_percent = cls.get_discount(quantity)
        discounted_price = total_price * (1 - discount_percent / 100)
        return round(discounted_price, 2), discount_percent


# Глобальный экземпляр конфигурации
config = Config()

# Добавляем BASE_DIR в config для совместимости
config.BASE_DIR = BASE_DIR
