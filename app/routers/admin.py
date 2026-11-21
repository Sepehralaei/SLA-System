import pyodbc
from datetime import datetime
import jdatetime
import io
import pandas as pd
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse 
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.dependencies import require_admin
from app.database import get_db_connection
from security import hash_password

# فرض بر این است که فایل ایمیل در app/services/email_service.py یا app/utils/email_config.py قرار دارد:
from email_config import generate_random_password, send_welcome_email

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    admin_user: dict = Depends(require_admin),
    conn: pyodbc.Connection = Depends(get_db_connection),
):
    cursor = conn.cursor()
    query = """
        SELECT user_id, username, email, is_admin, is_active, created_at, last_login_at
        FROM dbo.Users
        ORDER BY user_id DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    users_list = [
        {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "is_admin": bool(row[3]),
            "is_active": bool(row[4]),
            "created_at": str(row[5]) if row[5] else "-",
            "last_login_at": str(row[6]) if row[6] else "-",
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        request=request,
        name="Admin_users.html",
        context={
            "current_user": admin_user,
            "users": users_list,
            "is_admin": True,
        },
    )


@router.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    is_admin: bool = Form(False),
    admin_user: dict = Depends(require_admin),
    conn: pyodbc.Connection = Depends(get_db_connection),
):
    cursor = conn.cursor()
    clean_username = username.strip()
    clean_email = email.strip()

    # ۱. بررسی تکراری نبودن یوزرنیم یا ایمیل
    check_query = "SELECT user_id FROM dbo.Users WHERE username = ? OR email = ?"
    cursor.execute(check_query, (clean_username, clean_email))
    if cursor.fetchone():
        # دریافت مجدد لیست کاربران برای نمایش صحیح صفحه در صورت خطا
        cursor.execute("SELECT user_id, username, email, is_admin, is_active, created_at, last_login_at FROM dbo.Users ORDER BY user_id DESC")
        rows = cursor.fetchall()
        users_list = [
            {
                "user_id": row[0],
                "username": row[1],
                "email": row[2],
                "is_admin": bool(row[3]),
                "is_active": bool(row[4]),
                "created_at": str(row[5]) if row[5] else "-",
                "last_login_at": str(row[6]) if row[6] else "-",
            }
            for row in rows
        ]
        return templates.TemplateResponse(
            request=request,
            name="Admin_users.html",
            context={
                "current_user": admin_user,
                "users": users_list,
                "error_message": "Username or Email already exists.",
                "is_admin": True,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ۲. تولید رمز عبور تصادفی و امن
    raw_password = generate_random_password(length=10)

    # ۳. هش کردن رمز عبور تولید شده
    password_hash = hash_password(raw_password)

    # ۴. ثبت یوزر جدید در دیتابیس
    insert_query = """
        INSERT INTO dbo.Users (username, email, password_hash, is_admin, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, SYSDATETIME())
    """
    cursor.execute(
        insert_query,
        (
            clean_username,
            clean_email,
            password_hash,
            1 if is_admin else 0,
        ),
    )
    conn.commit()

    # ۵. ارسال ایمیل خوش‌آمدگویی در پس‌زمینه (Background Task)
    background_tasks.add_task(
        send_welcome_email,
        to_email=clean_email,
        username=clean_username,
        temp_password=raw_password,
        is_admin=is_admin,
    )

    return RedirectResponse(
        url="/admin/users?success=created",
        status_code=status.HTTP_303_SEE_OTHER,
    )

# یک تابع کمکی برای تبدیل امن تاریخ شمسی (YYYY-MM-DD) به میلادی
def jalali_to_gregorian(j_date_str: Optional[str]) -> Optional[str]:
    if not j_date_str:
        return None
    try:
        parts = [int(p) for p in j_date_str.strip().split("-")]
        if len(parts) == 3:
            g_date = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()
            return g_date.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None

@router.get("/admin/activity-logs", response_class=HTMLResponse)
async def get_user_activity_logs(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: dict = Depends(require_admin),
    conn: pyodbc.Connection = Depends(get_db_connection),
):
    g_from_date = jalali_to_gregorian(from_date)
    g_to_date = jalali_to_gregorian(to_date)

    cursor = conn.cursor()

    summary_query = """
        SELECT 
            username, 
            COUNT(*) AS total_downloads,
            MAX(created_at) AS last_activity
        FROM dbo.UserActivityLogs
        WHERE (? IS NULL OR CAST(created_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(created_at AS DATE) <= ?)
        GROUP BY username
        ORDER BY total_downloads DESC
    """
    cursor.execute(summary_query, (g_from_date, g_from_date, g_to_date, g_to_date))
    columns = [col[0] for col in cursor.description]
    user_stats = [dict(zip(columns, row)) for row in cursor.fetchall()]

    detail_query = """
        SELECT TOP 200
            username, 
            site_code, 
            start_date, 
            end_date, 
            created_at
        FROM dbo.UserActivityLogs
        WHERE (? IS NULL OR CAST(created_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(created_at AS DATE) <= ?)
        ORDER BY created_at DESC
    """
    cursor.execute(detail_query, (g_from_date, g_from_date, g_to_date, g_to_date))
    detail_columns = [col[0] for col in cursor.description]
    detailed_logs = [dict(zip(detail_columns, row)) for row in cursor.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="admin_activity.html",
        context={
            "user": user,
            "user_stats": user_stats,
            "detailed_logs": detailed_logs,
            "from_date": from_date,
            "to_date": to_date,
        }
    )

@router.get("/admin/activity-logs/export")
async def export_activity_logs_excel(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    user: dict = Depends(require_admin),
    conn: pyodbc.Connection = Depends(get_db_connection),
):
    # ۱. تبدیل تاریخ‌های شمسی به میلادی (مثل روت اصلی صفحه)
    g_from_date = jalali_to_gregorian(from_date)
    g_to_date = jalali_to_gregorian(to_date)

    cursor = conn.cursor()

    # ۲. خلاصه تعداد گزارش هر کاربر
    summary_query = """
        SELECT 
            username AS [User],
            COUNT(*) AS [Total Reports Generated],
            MAX(created_at) AS [Last Activity]
        FROM dbo.UserActivityLogs
        WHERE (? IS NULL OR CAST(created_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(created_at AS DATE) <= ?)
        GROUP BY username
        ORDER BY COUNT(*) DESC
    """
    cursor.execute(summary_query, (g_from_date, g_from_date, g_to_date, g_to_date))
    summary_columns = [col[0] for col in cursor.description]
    summary_rows = cursor.fetchall()

    # ۳. ریز لاگ‌ها (بدون TOP 200 تا کل داده‌های فیلترشده در اکسل بیاد)
    detail_query = """
        SELECT 
            username AS [User],
            site_code AS [Site Code],
            start_date AS [Report Start Date],
            end_date AS [Report End Date],
            created_at AS [Timestamp]
        FROM dbo.UserActivityLogs
        WHERE (? IS NULL OR CAST(created_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(created_at AS DATE) <= ?)
        ORDER BY created_at DESC
    """
    cursor.execute(detail_query, (g_from_date, g_from_date, g_to_date, g_to_date))
    detail_columns = [col[0] for col in cursor.description]
    detail_rows = cursor.fetchall()

    # ۴. ساخت دیتافریم‌ها
    df_summary = pd.DataFrame.from_records(summary_rows, columns=summary_columns)
    df_logs = pd.DataFrame.from_records(detail_rows, columns=detail_columns)

    if df_summary.empty:
        df_summary = pd.DataFrame(columns=["User", "Total Reports Generated", "Last Activity"])
    if df_logs.empty:
        df_logs = pd.DataFrame(columns=["User", "Site Code", "Report Start Date", "Report End Date", "Timestamp"])

    # ۵. نوشتن دو شیت در یک فایل اکسل (In-Memory)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Summary By User", index=False)
        df_logs.to_excel(writer, sheet_name="Activity Logs", index=False)
    output.seek(0)

    # ۶. نام فایل دانلودی
    filename = "Activity_Report.xlsx"
    if from_date or to_date:
        filename = f"Activity_Report_{from_date or 'start'}_to_{to_date or 'end'}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
