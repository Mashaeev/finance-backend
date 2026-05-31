"""
Роутер транзакций: создание, список, удаление.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg import Connection
from typing import List, Optional
from datetime import date

from database import get_connection
from schemas import TransactionCreate, TransactionOut
from auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["Транзакции"])


@router.post("/", response_model=TransactionOut, status_code=201)
async def create_transaction(
    data: TransactionCreate,
    conn: Connection = Depends(get_connection),
    current_user: dict = Depends(get_current_user),
):
    """Добавить новую транзакцию."""
    if current_user["role"] == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может создавать транзакции")
    row = await conn.fetchrow(
        """INSERT INTO transactions (user_id, category_id, type, amount, description, date)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, user_id, category_id, NULL::text AS category_name, type, amount, description, date, created_at""",
        current_user["user_id"],
        data.category_id,
        data.type.value,
        data.amount,
        data.description,
        data.date,
    )
    return dict(row)


@router.get("/", response_model=List[TransactionOut])
async def list_transactions(
    date_from: Optional[date] = Query(None, description="С даты (YYYY-MM-DD)"),
    date_to:   Optional[date] = Query(None, description="По дату (YYYY-MM-DD)"),
    type:      Optional[str]  = Query(None, description="income / expense"),
    limit:     int            = Query(50, ge=1, le=200),
    offset:    int            = Query(0, ge=0),
    conn: Connection          = Depends(get_connection),
    current_user: dict        = Depends(get_current_user),
):
    """Список транзакций с фильтрами. Admin и observer видят все."""
    is_admin_or_observer = current_user["role"] in ("admin", "observer")

    if is_admin_or_observer:
        filters = ["1=1"]
        params  = []
        idx = 1
    else:
        filters = ["t.user_id = $1"]
        params  = [current_user["user_id"]]
        idx = 2

    if date_from:
        filters.append(f"t.date >= ${idx}"); params.append(date_from); idx += 1
    if date_to:
        filters.append(f"t.date <= ${idx}"); params.append(date_to); idx += 1
    if type:
        filters.append(f"t.type = ${idx}"); params.append(type); idx += 1

    where = " AND ".join(filters)
    params += [limit, offset]

    rows = await conn.fetch(
        f"""SELECT t.id, t.user_id, t.category_id, c.name AS category_name,
                   t.type, t.amount, t.description, t.date, t.created_at,
                   u.username
            FROM transactions t
            JOIN categories c ON c.id = t.category_id
            JOIN users u ON u.id = t.user_id
            WHERE {where}
            ORDER BY t.date DESC, t.created_at DESC
            LIMIT ${idx} OFFSET ${idx+1}""",
        *params,
    )
    return [dict(r) for r in rows]


@router.put("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: int,
    data: TransactionCreate,
    conn: Connection        = Depends(get_connection),
    current_user: dict      = Depends(get_current_user),
):
    """Обновить транзакцию."""
    if current_user["role"] == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может редактировать транзакции")
    
    # Проверяем права (админ может редактировать любую, бухгалтер только свои)
    is_admin = current_user["role"] == "admin"
    if not is_admin:
        # Проверяем что транзакция принадлежит пользователю
        check = await conn.fetchrow(
            "SELECT user_id FROM transactions WHERE id=$1", transaction_id
        )
        if not check or check["user_id"] != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Нет прав на редактирование этой транзакции")
    
    # Обновляем транзакцию
    row = await conn.fetchrow(
        """UPDATE transactions 
           SET type=$1, amount=$2, category_id=$3, description=$4, date=$5
           WHERE id=$6
           RETURNING id, user_id, category_id, NULL::text AS category_name, type, amount, description, date, created_at""",
        data.type.value,
        data.amount,
        data.category_id,
        data.description,
        data.date,
        transaction_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    
    # Получаем имя категории
    if row["category_id"]:
        cat = await conn.fetchrow(
            "SELECT name FROM categories WHERE id=$1", row["category_id"]
        )
        row = dict(row)
        row["category_name"] = cat["name"] if cat else None
    
    return dict(row)


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    conn: Connection        = Depends(get_connection),
    current_user: dict      = Depends(get_current_user),
):
    """Удалить транзакцию. Администратор может удалить любую."""
    if current_user["role"] == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может удалять транзакции")
    is_admin = current_user["role"] == "admin"
    if is_admin:
        result = await conn.execute(
            "DELETE FROM transactions WHERE id=$1", transaction_id
        )
    else:
        result = await conn.execute(
            "DELETE FROM transactions WHERE id=$1 AND user_id=$2",
            transaction_id, current_user["user_id"],
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
