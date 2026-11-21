import os
import pyodbc
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db_connection
from app.dependencies import require_login  # گارد امنیتی
from app.services.database_service import get_data_from_sql
from app.services.date_service import jalali_to_gregorian
from app.services.excel_exporter import export_report
from app.services.outage_calculator import calculate_total_outage
from app.services.outage_filter import filter_outages_by_date

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user: dict = Depends(require_login),  # گارد لاگین: اگر لاگین نباشد خودکار به /login هدایت می‌شود
):
    # اطلاعات کاربر لاگین‌شده در متغیر user موجود است و می‌توانید به تمپلیت هم بفرستید
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user},
    )


@router.post("/generate")
async def generate_report(
    request: Request,
    site_code: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    user: dict = Depends(require_login),
    conn: pyodbc.Connection = Depends(get_db_connection),
):
    try:
        query = """
            SELECT site_name, start_time, end_time, time_delta
            FROM dbo.Sitelogs
        """
        df = get_data_from_sql(conn, query)

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail="Data could not be retrieved from the database",
            )

        g_start = jalali_to_gregorian(start_date)
        g_end = jalali_to_gregorian(end_date)

        filtered_df = filter_outages_by_date(df, g_start, g_end, "start_time")

        site_df = filtered_df[
            filtered_df["site_name"].str.contains(site_code, case=False, na=False)
        ]

        summary = calculate_total_outage(site_df)

        os.makedirs("reports", exist_ok=True)
        file_path = os.path.join("reports", f"{site_code}_report.xlsx")

        export_report(site_df, summary["total_duration"], file_path)

        print(">>> ABOUT TO LOG DOWNLOAD")
        print("user =", user)
        print("site_code =", site_code, "start_date =", start_date, "end_date =", end_date)

        try:
            cursor = conn.cursor()

            log_query = """
                INSERT INTO dbo.UserActivityLogs
                (user_id, username, site_code, start_date, end_date, created_at)
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """

            user_id = user.get("user_id") if isinstance(user, dict) else getattr(user, "user_id", None)
            username = user.get("username") if isinstance(user, dict) else getattr(user, "username", "Unknown")

            print(">>> user_id =", user_id)
            print(">>> username =", username)

            cursor.execute(log_query, (user_id, username, site_code, start_date, end_date))
            conn.commit()

            print(">>> LOG INSERT SUCCESS")

        except Exception as log_err:
            print(f"Error logging report generation: {log_err}")
            print(">>> LOGGING FAILED:", repr(log_err))

        return FileResponse(
            path=file_path,
            filename=f"Report_{site_code}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"X-Total-Downtime": str(summary["total_duration"])},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in processing: {str(e)}")
