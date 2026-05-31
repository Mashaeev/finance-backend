"""
Роутер авторизации: регистрация и вход.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from asyncpg import Connection

from database import get_connection
from schemas import RegisterRequest, LoginRequest, TokenResponse, UserOut, ChangePasswordRequest, ChangeRoleRequest
from auth import hash_password, verify_password, create_access_token, get_current_user, require_admin as get_current_admin

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, conn: Connection = Depends(get_connection)):
    """Регистрация нового пользователя."""
    # Проверяем уникальность
    existing = await conn.fetchrow(
        "SELECT id FROM users WHERE username=$1 OR email=$2", data.username, data.email
    )
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed = hash_password(data.password)
    row = await conn.fetchrow(
        """INSERT INTO users (username, email, password, role)
           VALUES ($1, $2, $3, 'observer')
           RETURNING id, role, username""",
        data.username, data.email, hashed,
    )

    token = create_access_token({"sub": str(row["id"]), "role": row["role"]})
    return TokenResponse(access_token=token, role=row["role"], username=row["username"])


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user=Depends(get_current_user),
    conn: Connection = Depends(get_connection),
):
    """Актуальные данные текущего пользователя (роль может измениться админом)."""
    row = await conn.fetchrow(
        "SELECT id, username, email, role, created_at FROM users WHERE id=$1",
        current_user["user_id"],
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return dict(row)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    current_user=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    """Список всех пользователей (только для администратора)."""
    rows = await conn.fetch(
        "SELECT id, username, email, role, created_at FROM users ORDER BY created_at"
    )
    return [dict(r) for r in rows]


@router.put("/users/me/password")
async def change_password(
    data: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    conn: Connection = Depends(get_connection),
):
    """Смена пароля текущего пользователя."""
    row = await conn.fetchrow("SELECT password FROM users WHERE id=$1", current_user["user_id"])
    if not row or not verify_password(data.old_password, row["password"]):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    hashed = hash_password(data.new_password)
    await conn.execute("UPDATE users SET password=$1 WHERE id=$2", hashed, current_user["user_id"])
    return {"message": "Пароль успешно изменён"}

@router.patch("/users/{user_id}/role", response_model=UserOut)
async def change_user_role(
    user_id: int,
    data: ChangeRoleRequest,
    current_user = Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    """Сменить роль пользователя (only admin)."""
    row = await conn.fetchrow(
        """UPDATE users SET role=$1 WHERE id=$2
           RETURNING id, username, email, role, created_at""",
        data.role.value, user_id,
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return dict(row)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, conn: Connection = Depends(get_connection)):
    """Вход по логину и паролю."""
    row = await conn.fetchrow(
        "SELECT id, password, role, username FROM users WHERE username=$1", data.username
    )
    if not row or not verify_password(data.password, row["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    token = create_access_token({"sub": str(row["id"]), "role": row["role"]})
    return TokenResponse(access_token=token, role=row["role"], username=row["username"])
