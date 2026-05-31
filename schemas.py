"""
Pydantic-схемы для валидации входящих/исходящих данных API.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ── Роли ─────────────────────────────────────────────────────────────────────
class UserRole(str, Enum):
    admin      = "admin"
    accountant = "accountant"
    observer   = "observer"


# ── Тип транзакции ────────────────────────────────────────────────────────────
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


# ── Auth ──────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    # role всегда observer при регистрации, admin меняет позже
    role: UserRole = UserRole.observer


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ── Пользователь ──────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime


class ChangeRoleRequest(BaseModel):
    role: UserRole


# ── Категории ─────────────────────────────────────────────────────────────────
class CategoryOut(BaseModel):
    id: int
    name: str
    type: str
    icon: Optional[str] = None


# ── Транзакции ────────────────────────────────────────────────────────────────
class TransactionCreate(BaseModel):
    category_id: int
    type: TransactionType
    amount: float
    description: Optional[str] = None
    date: date


class TransactionOut(BaseModel):
    id: int
    user_id: int
    category_id: int
    category_name: Optional[str] = None
    type: str
    amount: float
    description: Optional[str] = None
    date: date
    created_at: datetime
    username: Optional[str] = None


# ── Аналитика ─────────────────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_expense: float
    total_income: float
    net_profit: float
    expenses_today: float
    income_today: float
    net_profit_today: float


class ChartPoint(BaseModel):
    label: str          # день или неделя
    income: float
    expense: float


# ── Смена пароля ────────────────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=4)


# ── Налоги ─────────────────────────────────────────────────────────────────
class TaxSystem(str, Enum):
    usn_6  = "usn_6"   # УСН Доходы 6%
    usn_15 = "usn_15"  # УСН Доходы минус расходы 15%
    npd    = "npd"     # НПД (самозанятость)
    osno   = "osno"    # ОСНО (НДС 20% - заглушка)


class TaxSettingsOut(BaseModel):
    id: int
    tax_system: str
    tax_rate: float
    updated_by: Optional[int] = None
    updated_at: datetime


class TaxSettingsUpdate(BaseModel):
    tax_system: TaxSystem
    tax_rate: float = Field(..., ge=0, le=100)


class TaxResult(BaseModel):
    tax_system: str
    tax_rate: float
    period_start: date
    period_end: date
    income_total: float
    expense_total: float
    tax_base: float
    tax_amount: float
    details: Optional[dict] = None  # для НПД: доходы от физлиц/юрлиц


class TaxCalculationCreate(BaseModel):
    period_start: date
    period_end: date
    income_total: float
    expense_total: float
    tax_base: float
    tax_rate: float
    tax_amount: float
    tax_system: TaxSystem


class TaxCalculationOut(BaseModel):
    id: int
    user_id: int
    period_start: date
    period_end: date
    income_total: float
    expense_total: float
    tax_base: float
    tax_rate: float
    tax_amount: float
    tax_system: str
    calculated_at: datetime
