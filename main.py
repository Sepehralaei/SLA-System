import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies import require_admin
from fastapi import Depends
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.upload import router as upload_router
from app.routers.admin import router as admin_router
from app.routers import migration
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # یا لیست دامنه‌های مجاز شما
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Downtime"],  # ⬅️ این خط حیاتی است تا جاوااسکریپت بتواند هدر را بخواند
)

session_secret = os.getenv("SESSION_SECRET", "change-this-secret-in-production")

# ۲. ثبت روترها
app.include_router(dashboard_router)
# app.include_router(auth_router)
app.include_router(admin_router)  # 👈 این خط را حتماً اضافه کنید


app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="sla_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(upload_router)
app.include_router(migration.router)
