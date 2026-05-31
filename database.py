"""
Подключение к PostgreSQL через asyncpg.
Пул соединений создаётся при старте приложения и закрывается при завершении.
"""

import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finance_db")

# Глобальный пул соединений
pool: asyncpg.Pool = None


async def create_pool():
    """Инициализация пула при старте FastAPI."""
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)


async def close_pool():
    """Закрытие пула при остановке FastAPI."""
    global pool
    if pool:
        await pool.close()


async def get_connection():
    """Dependency-инъекция соединения в роутеры."""
    async with pool.acquire() as connection:
        yield connection


async def init_db():
    """Создание таблиц при первом запуске."""
    async with pool.acquire() as conn:
        # Пользователи
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'observer',
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Категории
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(20) NOT NULL,
                icon VARCHAR(50),
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Транзакции
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                type VARCHAR(20) NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                description TEXT,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Налоговые настройки
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tax_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                tax_system VARCHAR(50) DEFAULT 'usn_6',
                tax_rate DECIMAL(5,2) DEFAULT 6.0,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
