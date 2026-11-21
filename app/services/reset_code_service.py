import secrets
from datetime import datetime, timedelta


def generate_reset_code() -> str:
    """Generate a random 6-digit reset code (e.g. 048291)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def get_expiration_time(minutes: int = 2) -> datetime:
    """Return the expiration time (2 minutes from now by default)."""
    return datetime.now() + timedelta(minutes=minutes)
