"""
API для налоговой системы.
"""

from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from asyncpg import Connection

from database import get_connection
from auth import get_current_user, require_admin
from schemas import (
    TaxSettingsOut, TaxSettingsUpdate, TaxResult,
    TaxCalculationCreate, TaxCalculationOut
)

router = APIRouter(prefix="/tax", tags=["tax"])


# ── Настройки налогообложения (только для админа) ─────────────────────────────

@router.get("/settings", response_model=TaxSettingsOut)
async def get_tax_settings(
    conn: Connection = Depends(get_connection),
):
    """Получить текущие настройки налогообложения."""
    row = await conn.fetchrow("SELECT * FROM tax_settings ORDER BY id LIMIT 1")
    if not row:
        # Если настроек нет — создаём дефолтные
        row = await conn.fetchrow(
            """INSERT INTO tax_settings (tax_system, tax_rate)
               VALUES ('usn_6', 6.0)
               RETURNING *"""
        )
    return dict(row)


@router.put("/settings", response_model=TaxSettingsOut)
async def update_tax_settings(
    data: TaxSettingsUpdate,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
):
    """Обновить систему налогообложения (только админ)."""
    row = await conn.fetchrow(
        """UPDATE tax_settings
           SET tax_system=$1, tax_rate=$2, updated_at=NOW()
           WHERE id=(SELECT id FROM tax_settings ORDER BY id LIMIT 1)
           RETURNING *""",
        data.tax_system.value, data.tax_rate,
    )
    return dict(row)


# ── Расчёт налога ─────────────────────────────────────────────────────────────

@router.get("/calculate", response_model=TaxResult)
async def calculate_tax(
    date_from: Optional[date] = Query(None),
    date_to:   Optional[date] = Query(None),
    conn: Connection = Depends(get_connection),
    current_user: dict = Depends(get_current_user),
):
    """Рассчитать налог за период.
    Если даты не заданы — текущий месяц."""
    # Получаем настройки
    settings = await conn.fetchrow(
        "SELECT tax_system, tax_rate FROM tax_settings ORDER BY id LIMIT 1"
    )
    if not settings:
        # Дефолт
        tax_system = "usn_6"
        tax_rate = 6.0
    else:
        tax_system = settings["tax_system"]
        tax_rate = float(settings["tax_rate"])

    # Определяем период
    if not date_from or not date_to:
        today = datetime.now().date()
        date_from = today.replace(day=1)  # 1-е число текущего месяца
        date_to = today  # сегодня

    # Фильтр по пользователю (admin и observer видят все)
    is_admin_or_observer = current_user["role"] in ("admin", "observer")
    user_filter = "" if is_admin_or_observer else "AND t.user_id=$3"

    # Считаем доходы и расходы
    if is_admin_or_observer:
        income_row = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions
               WHERE type='income' AND date >= $1 AND date <= $2""",
            date_from, date_to,
        )
        expense_row = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions
               WHERE type='expense' AND date >= $1 AND date <= $2""",
            date_from, date_to,
        )
    else:
        income_row = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions
               WHERE type='income' AND date >= $1 AND date <= $2 AND user_id=$3""",
            date_from, date_to, current_user["user_id"],
        )
        expense_row = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions
               WHERE type='expense' AND date >= $1 AND date <= $2 AND user_id=$3""",
            date_from, date_to, current_user["user_id"],
        )

    income_total = float(income_row["total"])
    expense_total = float(expense_row["total"])

    # Расчёт налога в зависимости от системы
    tax_base = 0.0
    tax_amount = 0.0
    details = None

    if tax_system == "usn_6":
        # УСН Доходы 6%
        tax_base = income_total
        tax_amount = income_total * (tax_rate / 100)

    elif tax_system == "usn_15":
        # УСН Доходы минус расходы 15%
        tax_base = income_total - expense_total
        if tax_base < 0:
            tax_base = 0
            tax_amount = 0
        else:
            tax_amount = tax_base * (tax_rate / 100)

    elif tax_system == "npd":
        # НПД (самозанятость): 4% от физлиц + 6% от юрлиц
        # Важно: только доходы с указанным payer_type!
        if is_admin_or_observer:
            ind_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND payer_type='individual'""",
                date_from, date_to,
            )
            legal_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND payer_type='legal'""",
                date_from, date_to,
            )
            # Доходы без указания payer_type (NULL)
            null_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND payer_type IS NULL""",
                date_from, date_to,
            )
        else:
            ind_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND user_id=$3 AND payer_type='individual'""",
                date_from, date_to, current_user["user_id"],
            )
            legal_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND user_id=$3 AND payer_type='legal'""",
                date_from, date_to, current_user["user_id"],
            )
            # Доходы без указания payer_type (NULL)
            null_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM transactions
                   WHERE type='income' AND date >= $1 AND date <= $2 AND user_id=$3 AND payer_type IS NULL""",
                date_from, date_to, current_user["user_id"],
            )

        ind_income = float(ind_row["total"])
        legal_income = float(legal_row["total"])
        null_income = float(null_row["total"])
        # Налоговая база только от доходов с указанным payer_type
        tax_base = ind_income + legal_income
        # 4% от физлиц + 6% от юрлиц (фиксированные ставки НПД)
        tax_amount = (ind_income * 0.04) + (legal_income * 0.06)
        details = {
            "individual_income": ind_income, 
            "legal_income": legal_income,
            "null_income": null_income,
            "tax_rate_individual": 4.0,
            "tax_rate_legal": 6.0
        }

    elif tax_system == "osno":
        # ОСНО (НДС 20%) — заглушка
        tax_base = income_total
        tax_amount = income_total * 0.20

    return TaxResult(
        tax_system=tax_system,
        tax_rate=tax_rate,
        period_start=date_from,
        period_end=date_to,
        income_total=income_total,
        expense_total=expense_total,
        tax_base=tax_base,
        tax_amount=tax_amount,
        details=details,
    )


# ── Сохранение расчётов ─────────────────────────────────────────────────────────

@router.post("/calculations", response_model=TaxCalculationOut, status_code=201)
async def save_calculation(
    data: TaxCalculationCreate,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
):
    """Сохранить расчёт налога в историю."""
    row = await conn.fetchrow(
        """INSERT INTO tax_calculations
           (user_id, period_start, period_end, income_total, expense_total,
            tax_base, tax_rate, tax_amount, tax_system)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           RETURNING *""",
        current_user["user_id"],
        data.period_start, data.period_end,
        data.income_total, data.expense_total,
        data.tax_base, data.tax_rate, data.tax_amount,
        data.tax_system.value,
    )
    return dict(row)


@router.get("/calculations", response_model=list[TaxCalculationOut])
async def get_calculations(
    limit: int = Query(20, ge=1, le=100),
    conn: Connection = Depends(get_connection),
    current_user: dict = Depends(get_current_user),
):
    """Получить историю расчётов текущего пользователя."""
    rows = await conn.fetch(
        """SELECT * FROM tax_calculations
           WHERE user_id=$1
           ORDER BY calculated_at DESC
           LIMIT $2""",
        current_user["user_id"], limit,
    )
    return [dict(r) for r in rows]
