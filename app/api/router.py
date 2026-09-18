from fastapi import APIRouter
from app.api.auth import router as auth_router

api_router = APIRouter(prefix="/api")

# Подключаем auth эндпоинты -> сформируется /api/auth/...
api_router.include_router(auth_router)

# from app.api.polling import router as polling_router
# from app.api.projects import router as projects_router
# api_router.include_router(polling_router)
# api_router.include_router(projects_router)