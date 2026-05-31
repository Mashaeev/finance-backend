"""
Точка входа FastAPI-приложения.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_pool, close_pool, init_db
from auth import hash_password
from routers.auth_router         import router as auth_router
from routers.transactions_router import router as transactions_router
from routers.analytics_router    import router as analytics_router
from routers.categories_router   import router as categories_router
from routers.tax_router          import router as tax_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: открыть/закрыть пул БД."""
    await create_pool()
    # Создаём таблицы при первом запуске
    await init_db()
    # Создаём дефолтных пользователей
    await create_default_users()
    yield
    await close_pool()

async def create_default_users():
    """Создание admin и buhgalter при первом запуске."""
    from database import pool
    async with pool.acquire() as conn:
        # Создаём admin если нет
        existing = await conn.fetchrow("SELECT id FROM users WHERE username='admin'")
        if not existing:
            hashed = hash_password("admin")
            await conn.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES ($1, $2, $3, 'admin')",
                "admin", "admin@finance.ru", hashed
            )
            print("✓ Admin created: admin / admin")
        
        # Создаём buhgalter если нет
        existing2 = await conn.fetchrow("SELECT id FROM users WHERE username='buhgalter'")
        if not existing2:
            hashed2 = hash_password("buhgalter")
            await conn.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES ($1, $2, $3, 'accountant')",
                "buhgalter", "buhgalter@finance.ru", hashed2
            )
            print("✓ Accountant created: buhgalter / buhgalter")


app = FastAPI(
    title="Finance App API",
    description="REST API для приложения финансового учёта",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — разрешаем все источники (для мобильного приложения)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(analytics_router)
app.include_router(categories_router)
app.include_router(tax_router)


@app.get("/", tags=["Healthcheck"])
async def root():
    """Проверка работоспособности API."""
    return {"status": "ok", "message": "Finance App API работает"}
