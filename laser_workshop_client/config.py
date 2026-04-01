# ==================== МОДУЛЬ КОНФИГУРАЦИИ CLIENT ====================
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class ClientConfig:
    """Класс конфигурации клиента для подключения к серверу RPi"""
    
    # Основные настройки
    SECRET_KEY = os.getenv('SECRET_KEY', 'laser_workshop_client_secret_key_2026_change_this')
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() in ('true', '1', 'yes')
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5001'))  # Клиент на другом порту
    
    # HTTPS/SSL настройки
    USE_HTTPS = os.getenv('USE_HTTPS', 'False').lower() in ('true', '1', 'yes')
    CERT_FILE = os.getenv('CERT_FILE', 'certs/client.crt')
    KEY_FILE = os.getenv('KEY_FILE', 'certs/client.key')
    
    # Настройки SSL для подключения к серверу
    VERIFY_SERVER_SSL = os.getenv('VERIFY_SERVER_SSL', 'False').lower() in ('true', '1', 'yes')
    SERVER_CA_CERT = os.getenv('SERVER_CA_CERT', 'certs/server.crt')
    
    # Полные пути к сертификатам
    if not os.path.isabs(CERT_FILE):
        CERT_FILE = os.path.join(BASE_DIR, CERT_FILE)
    if not os.path.isabs(KEY_FILE):
        KEY_FILE = os.path.join(BASE_DIR, KEY_FILE)
    if not os.path.isabs(SERVER_CA_CERT):
        SERVER_CA_CERT = os.path.join(BASE_DIR, SERVER_CA_CERT)
    
    # Настройки сервера (RPi)
    SERVER_HOST = os.getenv('SERVER_HOST', '192.168.1.100')  # IP адрес Raspberry Pi
    SERVER_PORT = int(os.getenv('SERVER_PORT', '5000'))      # Порт сервера на RPi
    SERVER_URL = os.getenv('SERVER_URL', '')  # Полный URL, если задан
    SERVER_PROTOCOL = os.getenv('SERVER_PROTOCOL', 'https') if USE_HTTPS else os.getenv('SERVER_PROTOCOL', 'http')
    
    # База данных (локальный кэш)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_NAME = os.getenv('DB_NAME', 'client_cache.db')
    DB_PATH = os.path.join(BASE_DIR, DB_NAME)
    DB_BACKUP_DIR = os.path.join(BASE_DIR, os.getenv('DB_BACKUP_DIR', 'backups'))
    
    # Оптимизация производительности (клиент лёгкий)
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '3'))
    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', '2'))
    CACHE_SIZE = int(os.getenv('CACHE_SIZE_MB', '16')) * 1024 * 1024
    
    # Кэширование
    CACHE_TTL = int(os.getenv('CACHE_TTL_SECONDS', '60'))  # Короткий TTL для актуальности
    MAX_USER_STATES = int(os.getenv('MAX_USER_STATES', '100'))
    
    # Режим работы
    OFFLINE_MODE = os.getenv('OFFLINE_MODE', 'False').lower() in ('true', '1', 'yes')
    AUTO_SYNC = os.getenv('AUTO_SYNC', 'True').lower() in ('true', '1', 'yes')
    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL_SECONDS', '30'))
    
    # UI настройки
    THEME = os.getenv('THEME', 'dark')
    MOBILE_OPTIMIZED = os.getenv('MOBILE_OPTIMIZED', 'True').lower() in ('true', '1', 'yes')
    
    # JWT Токен
    JWT_EXPIRATION_DAYS = int(os.getenv('JWT_EXPIRATION_DAYS', '7'))
    
    @classmethod
    def get_server_url(cls):
        """Получение URL сервера"""
        if cls.SERVER_URL:
            return cls.SERVER_URL
        protocol = cls.SERVER_PROTOCOL if hasattr(cls, 'SERVER_PROTOCOL') else 'http'
        return f"{protocol}://{cls.SERVER_HOST}:{cls.SERVER_PORT}"
    
    @classmethod
    def is_offline_mode(cls):
        """Проверка режима офлайн"""
        return cls.OFFLINE_MODE


# Глобальный экземпляр конфигурации
config = ClientConfig()
