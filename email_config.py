import os
import secrets
import string
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")


def generate_random_password(length: int = 10) -> str:
    """
    Generates a secure random password containing uppercase, lowercase, digits, and symbols.
    """
    characters = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(characters) for _ in range(length))


def _send_email(message: EmailMessage) -> None:
    """
    Sends an email through Gmail SMTP.
    """

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise RuntimeError(
            "SMTP_EMAIL or SMTP_APP_PASSWORD is missing from .env"
        )

    print(f"[EMAIL] Sending email to: {message['To']}")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(message)

    print(f"[EMAIL] Successfully sent to: {message['To']}")


def send_welcome_email(
    to_email: str,
    username: str,
    temp_password: str,
    is_admin: bool = False,
) -> None:
    """
    Sends a welcome email containing initial credentials.
    """
    role_title = "Administrator" if is_admin else "Operator"
    message = EmailMessage()

    message["From"] = SMTP_EMAIL
    message["To"] = to_email
    message["Subject"] = "Welcome to SLA - Account Credentials"

    body = f"""Hello {username}

Welcome to SLA System!

Your account has been created by the administrator. Here are your temporary login details:

Username: {username}
Temporary Password: {temp_password}
Role: {role_title}

Please sign in and update your password if needed.

Best regards,
SLA Team
"""

    message.set_content(body)
    _send_email(message)


def send_reset_code_email(
    to_email: str,
    reset_code: str,
) -> None:
    """
    Sends a password reset code.
    """

    message = EmailMessage()

    message["From"] = SMTP_EMAIL
    message["To"] = to_email
    message["Subject"] = "Password Reset Code"

    body = f"""Hello,

We received a request to reset your password.

Your password reset code is:

{reset_code}

This code will expire in 10 minutes.

If you did not request a password reset, please ignore this email.

Best regards,
SLA Team
"""

    message.set_content(body)
    _send_email(message)
