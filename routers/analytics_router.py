"""
Роутер аналитики: дашборд и данные для графика.
"""

from fastapi import APIRouter, Depends, Query
from asyncpg import Connection
from typing import List, Optional
from datetime import date as DateType

from database import get_connection
from schemas import DashboardStats, ChartPoint
from auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Аналитика"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    today:     Optional[DateType] = Query(None, description="Дата клиента (YYYY-MM-DD)"),
    conn: Connection              = Depends(get_connection),
    current_user: dict            = Depends(get_current_user),
):
    """Виджеты главного экрана.
    today — локальная дата клиента (фикс timezone)."""
    is_admin_or_observer = current_user["role"] in ("admin", "observer")
    uid        = current_user["user_id"]
    today_date = today  # клиент передаёт свою локальную дату

    if is_admin_or_observer:
        row = await conn.fetchrow(
            """SELECT
                COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS total_expense,
                COALESCE(SUM(amount) FILTER (WHERE type='income'),  0) AS total_income,
                COALESCE(SUM(amount) FILTER (WHERE type='income'), 0) -
                COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS net_profit,
                COALESCE(SUM(amount) FILTER (WHERE type='expense' AND ($1::date IS NULL OR date=$1)), 0) AS expenses_today,
                COALESCE(SUM(amount) FILTER (WHERE type='income'  AND ($1::date IS NULL OR date=$1)), 0) AS income_today,
                COALESCE(SUM(amount) FILTER (WHERE type='income'  AND ($1::date IS NULL OR date=$1)), 0) -
                COALESCE(SUM(amount) FILTER (WHERE type='expense' AND ($1::date IS NULL OR date=$1)), 0) AS net_profit_today
               FROM transactions""",
            today_date,
        )
    else:
        row = await conn.fetchrow(
            """SELECT
                COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS total_expense,
                COALESCE(SUM(amount) FILTER (WHERE type='income'),  0) AS total_income,
                COALESCE(SUM(amount) FILTER (WHERE type='income'), 0) -
                COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS net_profit,
                COALESCE(SUM(amount) FILTER (WHERE type='expense' AND ($2::date IS NULL OR date=$2)), 0) AS expenses_today,
                COALESCE(SUM(amount) FILTER (WHERE type='income'  AND ($2::date IS NULL OR date=$2)), 0) AS income_today,
                COALESCE(SUM(amount) FILTER (WHERE type='income'  AND ($2::date IS NULL OR date=$2)), 0) -
                COALESCE(SUM(amount) FILTER (WHERE type='expense' AND ($2::date IS NULL OR date=$2)), 0) AS net_profit_today
               FROM transactions WHERE user_id=$1""",
            uid, today_date,
        )
    return DashboardStats(**dict(row))


@router.get("/chart", response_model=List[ChartPoint])
async def chart(
    period:    str                = Query("week", description="'week' или 'month'"),
    date_from: Optional[DateType] = Query(None),
    date_to:   Optional[DateType] = Query(None),
    conn: Connection              = Depends(get_connection),
    current_user: dict            = Depends(get_current_user),
):
    """
    Данные для BarChart.
    Если date_from/date_to заданы — фильтруем по ним (группировка по дням).
    Иначе: period='week' → 7 дней, 'month' → 30 дней.
    """
    is_admin_or_observer = current_user["role"] in ("admin", "observer")
    uid = current_user["user_id"]

    # Фильтр по пользователю
    user_filter = "" if is_admin_or_observer else "AND t.user_id=$1"

    if date_from and date_to:
        # Произвольный диапазон — группировка по дням
        if is_admin_or_observer:
            rows = await conn.fetch(
                f"""SELECT to_char(t.date, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM transactions t
                   WHERE t.date >= $1 AND t.date <= $2
                   GROUP BY t.date ORDER BY t.date""",
                date_from, date_to,
            )
        else:
            rows = await conn.fetch(
                f"""SELECT to_char(t.date, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM transactions t
                   WHERE t.user_id=$1 AND t.date >= $2 AND t.date <= $3
                   GROUP BY t.date ORDER BY t.date""",
                uid, date_from, date_to,
            )
    elif period == "week":
        # Всегда 7 столбцов (последние 7 дней), дни без транзакций = 0
        if is_admin_or_observer:
            rows = await conn.fetch(
                """SELECT to_char(d.day, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM generate_series(
                       CURRENT_DATE - INTERVAL '6 days',
                       CURRENT_DATE,
                       '1 day'::interval
                   ) AS d(day)
                   LEFT JOIN transactions t ON t.date = d.day::date
                   GROUP BY d.day ORDER BY d.day"""
            )
        else:
            rows = await conn.fetch(
                """SELECT to_char(d.day, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM generate_series(
                       CURRENT_DATE - INTERVAL '6 days',
                       CURRENT_DATE,
                       '1 day'::interval
                   ) AS d(day)
                   LEFT JOIN transactions t ON t.date = d.day::date AND t.user_id = $1
                   GROUP BY d.day ORDER BY d.day""",
                uid,
            )
    elif period == "all":
        # Всё время — одна пара столбцов (суммарный доход vs расход)
        if is_admin_or_observer:
            row = await conn.fetchrow(
                """SELECT
                    COALESCE(SUM(amount) FILTER (WHERE type='income'),  0) AS income,
                    COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS expense
                   FROM transactions"""
            )
        else:
            row = await conn.fetchrow(
                """SELECT
                    COALESCE(SUM(amount) FILTER (WHERE type='income'),  0) AS income,
                    COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS expense
                   FROM transactions WHERE user_id=$1""",
                uid,
            )
        return [ChartPoint(label='Всё время', income=float(row['income']), expense=float(row['expense']))]
    else:
        # month — всегда 4 столбца (4 недели), недели без транзакций = 0
        if is_admin_or_observer:
            rows = await conn.fetch(
                """SELECT to_char(w.week, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM generate_series(
                       date_trunc('week', CURRENT_DATE) - INTERVAL '3 weeks',
                       date_trunc('week', CURRENT_DATE),
                       '1 week'::interval
                   ) AS w(week)
                   LEFT JOIN transactions t
                       ON date_trunc('week', t.date) = w.week
                   GROUP BY w.week ORDER BY w.week"""
            )
        else:
            rows = await conn.fetch(
                """SELECT to_char(w.week, 'DD.MM') AS label,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='income'),  0) AS income,
                          COALESCE(SUM(t.amount) FILTER (WHERE t.type='expense'), 0) AS expense
                   FROM generate_series(
                       date_trunc('week', CURRENT_DATE) - INTERVAL '3 weeks',
                       date_trunc('week', CURRENT_DATE),
                       '1 week'::interval
                   ) AS w(week)
                   LEFT JOIN transactions t
                       ON date_trunc('week', t.date) = w.week AND t.user_id = $1
                   GROUP BY w.week ORDER BY w.week""",
                uid,
            )

    return [ChartPoint(**dict(r)) for r in rows]


@router.get("/categories/summary")
async def categories_summary(
    conn: Connection   = Depends(get_connection),
    current_user: dict = Depends(get_current_user),
):
    """Сводка расходов/доходов по категориям за текущий месяц."""
    uid = current_user["user_id"]
    rows = await conn.fetch(
        """SELECT c.name, t.type,
                  COALESCE(SUM(t.amount), 0) AS total
           FROM transactions t
           JOIN categories c ON c.id = t.category_id
           WHERE t.user_id=$1
             AND date_trunc('month', t.date) = date_trunc('month', CURRENT_DATE)
           GROUP BY c.name, t.type
           ORDER BY total DESC""",
        uid,
    )
    return [dict(r) for r in rows]
