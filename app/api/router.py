from fastapi import APIRouter

from app.api import auth, schedules, projects

api_router = APIRouter(prefix="/api/v1")

# Подключаем модули
api_router.include_router(auth.router)
api_router.include_router(schedules.router)
api_router.include_router(projects.router)