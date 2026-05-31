"""
Роутер категорий: просмотр и создание (только администратор).
"""

from fastapi import APIRouter, Depends, HTTPException
from asyncpg import Connection
from typing import List

from database import get_connection
from schemas import CategoryOut
from auth import get_current_user, require_admin

router = APIRouter(prefix="/categories", tags=["Категории"])


@router.get("/", response_model=List[CategoryOut])
async def list_categories(conn: Connection = Depends(get_connection),
                          _: dict = Depends(get_current_user)):
    """Вернуть все категории (доступно всем авторизованным)."""
    rows = await conn.fetch("SELECT id, name, type, icon FROM categories ORDER BY type, name")
    return [dict(r) for r in rows]


@router.post("/", response_model=CategoryOut, status_code=201)
async def create_category(
    name: str,
    type: str,
    icon: str = "category",
    conn: Connection = Depends(get_connection),
    _: dict = Depends(require_admin),   # только администратор
):
    """Создать новую категорию (только администратор)."""
    if type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="type должен быть 'income' или 'expense'")
    row = await conn.fetchrow(
        "INSERT INTO categories (name, type, icon) VALUES ($1, $2, $3) RETURNING id, name, type, icon",
        name, type, icon,
    )
    return dict(row)
