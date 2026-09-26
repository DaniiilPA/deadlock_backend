from fastapi import APIRouter

from app.api import auth, schedules, projects, dictionaries

api_router = APIRouter(prefix="/api/v1")

# Подключаем модули
api_router.include_router(auth.router)
api_router.include_router(schedules.router)
api_router.include_router(projects.router)
api_router.include_router(dictionaries.router)