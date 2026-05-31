"""Создание первого администратора в системе."""
import asyncio
import asyncpg
import os
from auth import hash_password

DATABASE_URL = os.getenv("DATABASE_URL")

async def create_admin():
    """Создаёт админа admin/admin123 если его нет."""
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        return
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Проверяем есть ли админ
    existing = await conn.fetchrow("SELECT id FROM users WHERE username='admin'")
    if existing:
        print("Admin already exists")
        await conn.close()
        return
    
    # Создаём админа
    hashed = hash_password("admin123")
    await conn.execute(
        """INSERT INTO users (username, email, password_hash, role)
           VALUES ($1, $2, $3, 'admin')""",
        "admin", "admin@finance.ru", hashed
    )
    print("Admin created: admin / admin")
    
    # Проверяем есть ли бухгалтер
    existing_buh = await conn.fetchrow("SELECT id FROM users WHERE username='buhgalter'")
    if not existing_buh:
        # Создаём бухгалтера
        hashed_buh = hash_password("buhgalter")
        await conn.execute(
            """INSERT INTO users (username, email, password_hash, role)
               VALUES ($1, $2, $3, 'accountant')""",
            "buhgalter", "buhgalter@finance.ru", hashed_buh
        )
        print("Accountant created: buhgalter / buhgalter")
    else:
        print("Accountant already exists")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_admin())
