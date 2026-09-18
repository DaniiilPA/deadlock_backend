from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    #старт
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


# Единый формат ошибок

# Перехват наших бизнес-ошибок (409 EmailAlreadyExists, 401 Unauthorized и т.д.)
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


# Перехват ошибок валидации FastAPI/Pydantic (приводим к стандарту 400 Bad Request)
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


# Подключаем роутер с префиксом /api
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)