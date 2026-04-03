# -*- coding: utf-8 -*-
"""
Модели базы данных
Определение всех таблиц и операций с БД
"""

import sqlite3
import os
from datetime import datetime


class DatabaseManager:
    """Менеджер подключений к базе данных"""
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    def get_connection(self):
        """Получение подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'manager',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица клиентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                phone TEXT,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                cashback REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                vk_id INTEGER NOT NULL,
                service_type TEXT,
                material_type TEXT,
                thickness REAL,
                area REAL,
                quantity INTEGER DEFAULT 1,
                price REAL,
                discount REAL DEFAULT 0.0,
                final_price REAL,
                status TEXT DEFAULT 'new',
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица услуг
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                base_price REAL NOT NULL,
                unit TEXT DEFAULT 'см²'
            )
        ''')
        
        # Таблица материалов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT,
                thickness REAL,
                price_per_unit REAL,
                stock_quantity INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица склада
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER,
                quantity INTEGER DEFAULT 0,
                min_quantity INTEGER DEFAULT 10,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        ''')
        
        # Таблица транзакций кэшбека
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cashback_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                order_id INTEGER,
                amount REAL,
                transaction_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        conn.commit()
        conn.close()


# Глобальный экземпляр
db_manager = None


def get_db():
    """Получение подключения к БД"""
    from laser_workshop.core.config.settings import Settings
    settings = Settings()
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация БД"""
    from laser_workshop.core.config.settings import Settings
    settings = Settings()
    manager = DatabaseManager(settings.DB_PATH)
    manager.init_db()
