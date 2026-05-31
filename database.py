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
