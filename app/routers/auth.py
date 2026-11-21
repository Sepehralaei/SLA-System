import traceback
from datetime import datetime

import pyodbc
from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db_connection
from app.services.reset_code_service import generate_reset_code, get_expiration_time
from email_config import send_reset_code_email, send_welcome_email
from security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ----------------------------- Login -----------------------------
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    conn = get_db_connection()

    if conn is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error_message": "Unable to connect to the database. Please try again later.",
                "username": username,
            },
            status_code=500,
        )

    cursor = conn.cursor()

    try:
        query = """
            SELECT user_id, username, password_hash, is_active, is_admin
            FROM dbo.Users
            WHERE username = ?
        """
        cursor.execute(query, (username,))
        user = cursor.fetchone()

        if user is None:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error_message": "Invalid username or password.",
                    "username": username,
                },
            )

        user_id, db_username, stored_password_hash, is_active, is_admin = user

        if not is_active:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error_message": "This account is inactive.",
                    "username": username,
                },
            )

        if not verify_password(password, stored_password_hash):
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error_message": "Invalid username or password.",
                    "username": username,
                },
            )

        request.session["user_id"] = user_id
        request.session["username"] = db_username
        request.session["is_admin"] = bool(is_admin)

        

        update_query = """
            UPDATE dbo.Users
            SET last_login_at = SYSDATETIME()
            WHERE user_id = ?
        """
        cursor.execute(update_query, (user_id,))
        conn.commit()

        return RedirectResponse(url="/", status_code=303)

    except Exception:
        conn.rollback()
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error_message": "An unexpected error occurred during login.",
                "username": username,
            },
            status_code=500,
        )

    finally:
        cursor.close()
        conn.close()


# ----------------------------- Logout -----------------------------
@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ----------------------------- Register -----------------------------
'''@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})


@router.post("/register")
async def register_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    username = username.strip()
    email = email.strip().lower()

    def error_response(msg: str):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error_message": msg,
                "username": username,
                "email": email,
            },
        )

    if password != confirm_password:
        return error_response("Passwords do not match.")

    if len(password) < 8:
        return error_response("Password must be at least 8 characters.")

    conn = get_db_connection()
    if conn is None:
        return error_response("Failed to connect to the database.")

    cursor = conn.cursor()

    try:
        check_query = """
            SELECT username, email
            FROM dbo.Users
            WHERE username = ? OR email = ?
        """
        cursor.execute(check_query, (username, email))
        existing_user = cursor.fetchone()

        if existing_user is not None:
            existing_username, existing_email = existing_user
            if existing_username and existing_username.lower() == username.lower():
                return error_response("Username already exists.")
            if existing_email and existing_email.lower() == email.lower():
                return error_response("Email already exists.")

        password_hash = hash_password(password)

        insert_query = """
            INSERT INTO dbo.Users
                (username, email, password_hash, is_active)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(insert_query, (username, email, password_hash, True))
        conn.commit()

        background_tasks.add_task(send_welcome_email, email, username)

        return RedirectResponse(url="/login", status_code=303)

    except Exception as e:
        conn.rollback()
        return error_response(f"Registration error: {str(e)}")

    finally:
        cursor.close()
        conn.close()
'''

# ----------------------------- Forgot Password -----------------------------
@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="forgot_password.html", context={}
    )


@router.post("/forgot-password")
async def forgot_password_submit(request: Request, identifier: str = Form(...)):
    conn = None

    try:
        identifier = identifier.strip()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, email
            FROM Users
            WHERE username = ? OR email = ?
            """,
            (identifier, identifier),
        )
        user = cursor.fetchone()

        if user is None:
            return templates.TemplateResponse(
                request=request,
                name="forgot_password.html",
                context={"message": "User not found!"},
            )

        user_id, user_email = user

        reset_code = generate_reset_code()
        expires_at = get_expiration_time(minutes=10)

        cursor.execute(
            """
            INSERT INTO PasswordResetCodes
                (user_id, email, reset_code, expires_at, is_used)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, user_email, reset_code, expires_at, 0),
        )
        conn.commit()

        send_reset_code_email(to_email=user_email, reset_code=reset_code)

        request.session["reset_email"] = user_email
        request.session["reset_username"] = identifier

        return templates.TemplateResponse(request=request, name="verify_reset_code.html")

    except pyodbc.Error as error:
        if conn is not None:
            conn.rollback()
        print(f"Database error in forgot-password: {error}")
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={"message": "A database error occurred. Please try again later."},
        )

    except Exception as error:
        if conn is not None:
            conn.rollback()
        print(f"Unexpected error in forgot-password: {error}")
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={"message": "Something went wrong. Please try again later."},
        )

    finally:
        if conn is not None:
            conn.close()


@router.post("/forgot-password/verify")
async def verify_code_submit(request: Request, code: str = Form(...)):
    email = request.session.get("reset_email")
    if not email:
        return {"error": "Session expired or invalid"}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT id
            FROM PasswordResetCodes
            WHERE email = ? AND reset_code = ? AND is_used = 0
            AND expires_at > GETDATE()
        """
        cursor.execute(query, (email, code))
        code_record = cursor.fetchone()

        if code_record:
            request.session["can_reset"] = True
            return templates.TemplateResponse(
                request=request, name="reset_password.html", context={}
            )

        return templates.TemplateResponse(
            request=request,
            name="verify_reset_code.html",
            context={"error": "Invalid or expired code."},
        )

    except Exception as e:
        print(f"Error in verification: {e}")
        return {"error": "Database error"}

    finally:
        if conn:
            conn.close()


@router.post("/forgot-password/resend-code")
async def resend_password_code(
    request: Request,
    username: str = Form(""),
    email: str = Form(""),
):
    username = (username or request.session.get("reset_username", "")).strip()
    email = (email or request.session.get("reset_email", "")).strip()

    if not username and not email:
        return templates.TemplateResponse(
            request=request,
            name="verify_reset_code.html",
            context={
                "username": "",
                "email": "",
                "message": "User information is missing. Please start again.",
                "msg_type": "error",
            },
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if username:
            cursor.execute(
                """
                SELECT user_id, username, email
                FROM Users
                WHERE username = ?
                """,
                (username,),
            )
        else:
            cursor.execute(
                """
                SELECT user_id, username, email
                FROM Users
                WHERE email = ?
                """,
                (email,),
            )

        user = cursor.fetchone()

        if not user:
            return templates.TemplateResponse(
                request=request,
                name="verify_reset_code.html",
                context={
                    "username": username,
                    "email": email,
                    "message": "User was not found.",
                    "msg_type": "error",
                },
            )

        user_id, user_username, user_email = user

        new_code = generate_reset_code()
        now = datetime.now()
        expires_at = get_expiration_time(minutes=2)

        cursor.execute(
            """
            UPDATE PasswordResetCodes
            SET is_used = 1
            WHERE user_id = ? AND is_used = 0
            """,
            (user_id,),
        )

        cursor.execute(
            """
            INSERT INTO PasswordResetCodes
                (user_id, email, reset_code, expires_at, is_used, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (user_id, user_email, new_code, expires_at, now),
        )

        conn.commit()

        send_reset_code_email(user_email, new_code)

        return templates.TemplateResponse(
            request=request,
            name="verify_reset_code.html",
            context={
                "username": user_username,
                "email": user_email,
                "message": "A new verification code has been sent to your email.",
                "msg_type": "success",
            },
        )

    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"Resend password code error: {exc}")
        return templates.TemplateResponse(
            request=request,
            name="verify_reset_code.html",
            context={
                "username": username,
                "email": email,
                "message": "Could not send a new code. Please try again.",
                "msg_type": "error",
            },
        )

    finally:
        if conn:
            conn.close()


@router.post("/forgot-password/reset")
async def reset_password_submit(
    request: Request,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if request.session.get("can_reset") is not True:
        return RedirectResponse(url="/forgot-password", status_code=303)

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={"message": "Passwords do not match."},
            status_code=400,
        )

    email = request.session.get("reset_email")

    if not email:
        return RedirectResponse(url="/forgot-password", status_code=303)

    if not isinstance(email, str):
        print("Invalid reset_email value:", repr(email))
        print("Invalid reset_email type:", type(email))
        return templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={"message": "Invalid password reset session."},
            status_code=400,
        )

    conn = None
    cursor = None

    try:
        hashed_pwd = hash_password(new_password)

        print("email:", repr(email))
        print("email type:", type(email))
        print("hashed_pwd type:", type(hashed_pwd))
        print("hashed_pwd preview:", repr(hashed_pwd[:30]))

        if not isinstance(hashed_pwd, str):
            raise TypeError(
                f"hash_password must return str, but returned {type(hashed_pwd).__name__}"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE Users
            SET password_hash = ?
            WHERE email = ?
            """,
            hashed_pwd,
            email,
        )

        updated_rows = cursor.rowcount
        print("Updated Users rows:", updated_rows)

        if updated_rows == 0:
            conn.rollback()
            return templates.TemplateResponse(
                request=request,
                name="reset_password.html",
                context={"message": "No user was found for this email."},
                status_code=404,
            )

        cursor.execute(
            """
            UPDATE PasswordResetCodes
            SET is_used = 1
            WHERE email = ? AND is_used = 0
            """,
            email,
        )

        conn.commit()
        print("Password updated successfully.")

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        print("Error while updating password:")
        print("Exception type:", type(exc).__name__)
        print("Exception message:", str(exc))
        traceback.print_exc()

        return {
            "error": "Database error",
            "exception_type": type(exc).__name__,
            "detail": str(exc),
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    request.session.pop("reset_email", None)
    request.session.pop("reset_username", None)
    request.session.pop("can_reset", None)
    request.session["success_message"] = "Password reset successfully."

    return RedirectResponse(url="/login", status_code=303)
