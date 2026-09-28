# Сервис мониторинга строительных площадок (Backend)

Бэкенд-сервис и фоновый воркер видеоаналитики для автоматизированного контроля за объектами капитального строительства. Система сопоставляет видеопотоки со стройплощадок с утвержденным календарным планом, контролирует фактическое наличие техники на текущем этапе, фиксирует простои и выявляет регламентные отклонения.

---

## Ссылки на компоненты проекта

* **Репозиторий фронтенда:** [ссылка на фронтенд](https://github.com/...)
* **Веса модели детекции (best.pt):** [ссылка на скачивание](https://...)
* **Документация и презентация:** [ссылка на документ](https://...)

---

## Стек технологий

* **Язык разработки:** Python 3.11
* **Web-фреймворк:** FastAPI, Uvicorn
* **База данных:** PostgreSQL 16
* **ORM и миграции:** SQLAlchemy 2.0 (asyncio + asyncpg), Alembic
* **ML / Computer Vision:** PyTorch, Torchvision, Ultralytics (YOLO)
* **Фоновые процессы:** APScheduler, Asyncio
* **Контейнеризация:** Docker, Docker Compose

---

## Архитектура контейнеров

В конфигурации `docker-compose.yml` развернуты 4 сервиса:

| Контейнер | Назначение | Порт |
| :--- | :--- | :--- |
| `app` | REST API сервис (бизнес-логика, графики, инциденты) | 8000 |
| `worker` | Фоновый процесс видеоаналитики и расчета матричных окон | — |
| `postgres` | База данных PostgreSQL | 5432 |
| `mock_camera` | Локальный эмулятор камеры (циклическая отдача тестовых кадров) | 8081 |

---

## Start

### 1. Подготовка окружения
Создайте в корне проекта файл `.env` со следующими параметрами:

```env
APP_NAME="Construction Monitoring Service"
DEBUG=True

# Подключение к PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@postgres:5432/app_db

# Безопасность и JWT
JWT_SECRET_KEY=change-this-to-a-very-secret-random-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_SECONDS=900
REFRESH_TOKEN_EXPIRE_SECONDS=2592000

# Настройки сессионных cookie
COOKIE_NAME=refresh_token
COOKIE_PATH=/api/v1/auth
COOKIE_SECURE=False
COOKIE_SAMESITE=strict
```

### 2. Сборка и запуск контейнеров

```
docker compose up -d --build
```