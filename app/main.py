from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.security import AppException
from app.db.session import engine
from app.db.models import Base

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт: создаем папку под статику и проверяем БД
    os.makedirs("storage", exist_ok=True)
    logger.info("Проверка подключения к бд")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Успешное подключение к бд")
    except Exception as e:
        logger.critical(f"Не удалось подключиться к бд: {e}")
        raise e  

    yield

    # Остановка
    logger.info("Закрытие пула с бд")
    await engine.dispose()
    logger.info("Пул закрыт")


# Инициализация FastAPI приложения
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # разрешает отправку кук и Bearer-токена
    allow_methods=["*"],
    allow_headers=["*"],
)


# Статика

app.mount("/static", StaticFiles(directory="storage"), name="static")

# Ошибки

# Перехватбизнес-ошибок (409, 401 и т.д.)
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


# Перехват стандартных HTTPException (например, 403 из проверки прав или 404)
# Приводим к формату {"error": {...}}
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


# Перехват ошибок валидации FastAPI/Pydantic
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        field_loc = [str(loc) for loc in err["loc"] if loc not in ("body", "query", "path")]
        field_name = ".".join(field_loc) if field_loc else "body"
        details.append(
            {
                "field": field_name,
                "message": err["msg"],
            }
        )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "BAD_REQUEST",
                "message": "Ошибка валидации переданных данных",
                "details": details,
            }
        },
    )


# Подключаем роутер
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)