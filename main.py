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
    # Создаём дефолтные категории
    await create_default_categories()
    yield
    await close_pool()

async def create_default_categories():
    """Создание дефолтных категорий при первом запуске."""
    from database import pool
    async with pool.acquire() as conn:
        # Очищаем все данные для чистого старта
        await conn.execute("DELETE FROM transactions")
        await conn.execute("DELETE FROM tax_settings")
        await conn.execute("DELETE FROM categories WHERE user_id IS NULL")
        
        # Дефолтные категории расходов (из ТЗ)
        expense_categories = [
            ("Аренда", "expense", "🏠", None),
            ("Зарплата", "expense", "�", None),
            ("Товары", "expense", "🛒", None),
            ("Налоги", "expense", "📄", None),
            ("Прочие расходы", "expense", "�", None),
        ]
        
        # Дефолтные категории доходов (из ТЗ)
        income_categories = [
            ("Выручка", "income", "�", None),
            ("Займы", "income", "🤝", None),
            ("Инвестиции", "income", "📈", None),
            ("Прочие доходы", "income", "💵", None),
        ]
        
        for cat in expense_categories + income_categories:
            await conn.execute(
                "INSERT INTO categories (name, type, icon, user_id) VALUES ($1, $2, $3, $4)",
                cat[0], cat[1], cat[2], cat[3]
            )
        
        print(f"✓ Created {len(expense_categories)} expense and {len(income_categories)} income categories")

# Убрано - тестовые транзакции не нужны, пользователи создают сами
async def create_default_transactions(conn):
    """Создание тестовых транзакций для демонстрации."""
    # Проверяем есть ли транзакции
    count = await conn.fetchval("SELECT COUNT(*) FROM transactions")
    if count > 0:
        return
    
    # Получаем admin ID
    admin = await conn.fetchrow("SELECT id FROM users WHERE username='admin'")
    if not admin:
        return
    
    admin_id = admin["id"]
    
    # Получаем ID категорий
    cats = await conn.fetch("SELECT id, name, type FROM categories")
    cat_map = {c["name"]: c["id"] for c in cats}
    
    # Тестовые транзакции (30 дней назад до сегодня)
    from datetime import datetime, timedelta
    today = datetime.now()
    
    transactions = [
        # Доходы (из ТЗ)
        (admin_id, cat_map.get("Выручка"), "income", 150000, "Продажа товаров", today - timedelta(days=5)),
        (admin_id, cat_map.get("Выручка"), "income", 85000, "Услуги клиентам", today - timedelta(days=12)),
        (admin_id, cat_map.get("Займы"), "income", 50000, "Кредит для бизнеса", today - timedelta(days=20)),
        (admin_id, cat_map.get("Инвестиции"), "income", 15000, "Дивиденды", today - timedelta(days=15)),
        (admin_id, cat_map.get("Прочие доходы"), "income", 8000, "Продажа оборудования", today - timedelta(days=8)),
        
        # Расходы (из ТЗ)
        (admin_id, cat_map.get("Аренда"), "expense", 45000, "Аренда офиса", today - timedelta(days=3)),
        (admin_id, cat_map.get("Аренда"), "expense", 15000, "Складское помещение", today - timedelta(days=18)),
        (admin_id, cat_map.get("Зарплата"), "expense", 120000, "Зарплата сотрудникам", today - timedelta(days=5)),
        (admin_id, cat_map.get("Зарплата"), "expense", 25000, "Премии", today - timedelta(days=10)),
        (admin_id, cat_map.get("Товары"), "expense", 65000, "Закупка товара", today - timedelta(days=7)),
        (admin_id, cat_map.get("Товары"), "expense", 28000, "Закупка сырья", today - timedelta(days=14)),
        (admin_id, cat_map.get("Налоги"), "expense", 25000, "Налог на прибыль", today - timedelta(days=25)),
        (admin_id, cat_map.get("Налоги"), "expense", 15000, "Страховые взносы", today - timedelta(days=22)),
        (admin_id, cat_map.get("Прочие расходы"), "expense", 8000, "Транспорт", today - timedelta(days=6)),
        (admin_id, cat_map.get("Прочие расходы"), "expense", 12000, "Реклама", today - timedelta(days=11)),
        (admin_id, cat_map.get("Прочие расходы"), "expense", 3500, "Связь и интернет", today - timedelta(days=16)),
    ]
    
    for t in transactions:
        await conn.execute(
            """INSERT INTO transactions (user_id, category_id, type, amount, description, date)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            t[0], t[1], t[2], t[3], t[4], t[5]
        )
    
    print(f"✓ Created {len(transactions)} test transactions")

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
