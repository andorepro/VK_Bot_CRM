"""
Конфигурация приложения
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# База данных
DB_PATH = os.path.join(BASE_DIR, 'data', 'laser_workshop.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')

# VK API
VK_API_TOKEN = os.getenv('VK_API_TOKEN', '')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID', '0'))

# Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
DEBUG = True
HOST = '0.0.0.0'
PORT = 5000

# SSL
SSL_CERT = os.path.join(BASE_DIR, 'certs', 'cert.pem')
SSL_KEY = os.path.join(BASE_DIR, 'certs', 'key.pem')
USE_SSL = False

# Кэшбек
CASHBACK_PERCENT = 5  # 5% баллами

# Скидки за опт
BULK_DISCOUNTS = {
    10: 0.05,   # 5% от 10 шт
    20: 0.10,   # 10% от 20 шт
    50: 0.15,   # 15% от 50 шт
    100: 0.20   # 20% от 100 шт
}

# Станки (внутреннее использование, не показывается клиентам)
MACHINES = {
    'jpt_m7_60w': {
        'name': 'JPT M7 60W',
        'type': 'fiber_marker',
        'description': 'Оптоволоконный лазер для металлов',
        'power': 60,
        'materials': ['metal', 'anodized_aluminum']
    },
    'ortur_lm3_10w': {
        'name': 'Ortur LM3 10W',
        'type': 'diode_engraver',
        'description': 'Диодный гравёр для неметаллов',
        'power': 10,
        'materials': ['wood', 'leather', 'acrylic', 'plastic', 'glass']
    }
}

# Типы расчётов
CALC_TYPES = [
    ('fixed', 'Штучный товар'),
    ('area_cm2', 'Площадь см²'),
    ('meter_thickness', 'Резка по толщине'),
    ('per_minute', 'Поминутная оплата'),
    ('per_char', 'За символ'),
    ('vector_length', 'Длина вектора'),
    ('setup_batch', 'B2B тираж'),
    ('photo_raster', 'Фото растр'),
    ('cylindrical', 'Цилиндрические объекты'),
    ('volume_3d', '3D клише'),
    ('material_and_cut', 'Материал + Резка')
]

# Статусы заказов
ORDER_STATUSES = [
    ('new', 'Новый'),
    ('processing', 'В работе'),
    ('done', 'Готов'),
    ('delivered', 'Выдан')
]

# Приоритеты заказов
ORDER_PRIORITIES = [
    ('normal', 'Обычный'),
    ('urgent', 'Срочно'),
    ('deferred', 'Отложенный')
]
