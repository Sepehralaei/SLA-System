from pwdlib import PasswordHash

# تغییر نام متغیر برای جلوگیری از تداخل نام با فیلدهای دیتابیس
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Receives a plain password and returns a secure hash as a string.
    Never save the plain password in the database.
    """
    # تبدیل صریح خروجی به رشته (str) برای ذخیره‌سازی بدون خطا در SQL Server
    return str(password_hasher.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compares the password entered by the user
    with the stored password hash.
    """
    return password_hasher.verify(plain_password, hashed_password)
