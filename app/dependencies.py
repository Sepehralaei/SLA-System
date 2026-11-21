import pyodbc
from fastapi import Depends, HTTPException, Request, status

# ایمپورت تابع مدیریت کانکشن دیتابیس
from app.database import get_db_connection


async def get_current_user(
    request: Request,
    conn: pyodbc.Connection = Depends(get_db_connection),
) -> dict:
    """Dependency پایه برای احراز هویت و واکشی وضعیت زنده کاربر از دیتابیس"""
    user_id = request.session.get("user_id")

    # ۱. اگر سشن وجود نداشت، هدایت به صفحه لاگین
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    # ۲. استعلام وضعیت کاربر از دیتابیس برای اطمینان از فعال بودن و صحت نقش
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, username, email, is_admin, is_active
        FROM dbo.Users
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()

    # ۳. اگر کاربر در دیتابیس حذف شده بود یا غیرفعال بود
    if not row or not row[4]:  # row[4] = is_active
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "is_admin": bool(row[3]),
        "is_active": bool(row[4]),
    }


async def require_login(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """گارد امنیتی برای دسترسی کاربران واردشده (عادی و ادمین)"""
    return current_user


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """گارد امنیتی اختصاصی برای دسترسی‌های حساس (فقط ادمین)"""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Forbidden: You do not have administrator privileges.",
        )
    return current_user
