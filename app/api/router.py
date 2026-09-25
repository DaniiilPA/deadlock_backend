from fastapi import APIRouter

from app.api import auth, schedules

api_router = APIRouter(prefix="/api")

# Подключаем модули
api_router.include_router(auth.router)
api_router.include_router(schedules.router)
