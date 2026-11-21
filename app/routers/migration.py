import sys
import os

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse


# تعریف آبجکت templates و معرفی پوشه فایل‌های html
templates = Jinja2Templates(directory="templates")

# اگر تابع لاگین نیاز داری، از dependencies فقط همان کاربر را بخوان:
from app.dependencies import get_current_user

router = APIRouter(prefix="/migration", tags=["migration"])


@router.get("/sla-migration-calc", response_class=HTMLResponse)
async def migration_calc(
    request: Request, 
    current_user: dict = Depends(get_current_user)
):
    return templates.TemplateResponse(
        request,
        "Time-Calculation.html", 
        {"request": request, "current_user": current_user}
    )
