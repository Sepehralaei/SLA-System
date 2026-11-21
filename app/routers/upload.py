import hashlib
import io
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db_connection
from app.dependencies import require_login
from app.services.database_service import (
    file_was_uploaded,
    get_recent_uploads,
    log_upload_history,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def load_recent_uploads() -> List[Dict]:
    conn = get_db_connection()
    if conn is None:
        return []

    try:
        return get_recent_uploads(conn, limit=5)
    except Exception as exc:
        print(f"Recent uploads error: {exc}")
        return []
    finally:
        conn.close()


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user: dict = Depends(require_login)):
    """توسط Depends(require_login) احراز هویت کنترل می‌شود"""
    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "user": user,
            "recent_uploads": load_recent_uploads(),
        },
    )


@router.post("/upload_data")
async def handle_upload(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_login),
):
    """احراز هویت با Depends و دریافت فایل"""
    print(f"DEBUG: File received: {file.filename}, Content Type: {file.content_type}")

    def render_upload_page(message: str, is_error: bool):
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={
                "user": user,
                "message": message,
                "is_error": is_error,
                "recent_uploads": load_recent_uploads(),
            },
        )

    if not file.filename:
        return render_upload_page("No file was selected.", True)

    allowed_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(allowed_extensions):
        return render_upload_page("Only CSV and Excel files are allowed.", True)

    conn = get_db_connection()
    if conn is None:
        return render_upload_page("Failed to connect to the database.", True)

    cursor = conn.cursor()

    try:
        contents = await file.read()
        if not contents:
            return render_upload_page("Uploaded file is empty.", True)

        file_hash = hashlib.sha256(contents).hexdigest()

        if file_was_uploaded(conn, file_hash):
            return render_upload_page(
                "This file has already been uploaded.",
                True,
            )

        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl")

        if df.empty:
            return render_upload_page("Uploaded file has no data.", True)

        df.columns = df.columns.astype(str).str.strip()
        required_columns = ["site_name", "start_time", "end_time", "time_delta"]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return render_upload_page(
                f"Missing columns: {', '.join(missing_columns)}", True
            )

        df = df[required_columns].copy()
        df = df.where(pd.notnull(df), None)

        date_values = (
            df["start_time"]
            .dropna()
            .astype(str)
            .str.strip()
            .str[:10]
        )

        data_start_date = date_values.min() if not date_values.empty else None
        data_end_date = date_values.max() if not date_values.empty else None

        insert_query = """
            INSERT INTO dbo.Sitelogs (site_name, start_time, end_time, time_delta)
            VALUES (?, ?, ?, ?)
        """

        data_to_insert = [
            (row["site_name"], row["start_time"], row["end_time"], row["time_delta"])
            for _, row in df.iterrows()
        ]

        if not data_to_insert:
            return render_upload_page("There are no valid rows to upload.", True)

        cursor.fast_executemany = True
        cursor.executemany(insert_query, data_to_insert)

        uploaded_by = (
            user.get("username")
            or user.get("email")
            or str(user.get("user_id") or "Unknown")
        )

        log_upload_history(
            conn=conn,
            filename=file.filename,
            file_hash=file_hash,
            uploaded_by=uploaded_by,
            data_start_date=data_start_date,
            data_end_date=data_end_date,
            record_count=len(data_to_insert),
        )

        conn.commit()

        return render_upload_page("File uploaded successfully.", False)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Upload error: {e}")
        return render_upload_page("File upload failed.", True)

    finally:
        cursor.close()
        conn.close()
