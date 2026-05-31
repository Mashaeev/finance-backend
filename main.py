"""
Точка входа FastAPI-приложения.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_pool, close_pool
from routers.auth_router         import router as auth_router
from routers.transactions_router import router as transactions_router
from routers.analytics_router    import router as analytics_router
from routers.categories_router   import router as categories_router
from routers.tax_router          import router as tax_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: открыть/закрыть пул БД."""
    await create_pool()
    yield
    await close_pool()


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
