"""
Конфигурация приложения и подключение к БД.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from laser_workshop.core.database.models import Base


class Config:
    """Конфигурация приложения"""
    
    # База данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///laser_workshop.db')
    
    # VK Bot
    VK_TOKEN = os.getenv('VK_TOKEN', '')
    VK_API_VERSION = '5.131'
    
    # Admin Panel
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ADMIN_LOGIN = os.getenv('ADMIN_LOGIN', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    # App settings
    DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


def get_engine():
    """Создание движка БД"""
    connect_args = {}
    if Config.DATABASE_URL.startswith('sqlite'):
        connect_args['check_same_thread'] = False
    
    engine = create_engine(
        Config.DATABASE_URL,
        connect_args=connect_args,
        echo=Config.DEBUG
    )
    return engine


def init_db_schema(engine):
    """Инициализация схемы БД"""
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine):
    """Фабрика сессий"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return scoped_session(SessionLocal)


# Глобальные объекты
engine = get_engine()
SessionLocal = get_session_factory(engine)


def get_db():
    """Получение сессии БД (для зависимостей)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
