
# Application Settings

APP_NAME="Auth Service"
DEBUG=True

# Database (PostgreSQL with Asyncpg)

# Формат: postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app_db


# Security & JWT Settings

# Сгенерировать надежный ключ можно командой:
# python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=change-this-to-a-very-secret-random-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_SECONDS=900               # 15 минут


# Cookies & Refresh Token Settings

REFRESH_TOKEN_EXPIRE_SECONDS=2592000          # 30 дней (Max-Age)
COOKIE_NAME=refresh_token
COOKIE_PATH=/api/v1/auth
COOKIE_SAMESITE=strict

# ВАЖНО ДЛЯ РАЗРАБОТКИ:
# - При локальной разработке по обычному HTTP (http://localhost:8000) ставить False, 
#   иначе браузер откажется сохранять куку
# - Для Production (с HTTPS) обязательно ставить True
COOKIE_SECURE=False




docker compose exec app alembic revision --autogenerate -m "initial_schema"
docker compose exec app alembic upgrade head
docker compose exec app python seed_db.py
docker compose exec app python test_all.py

docker compose exec app alembic revision --autogenerate -m "add_critical_path_and_allowed_equipment"
docker compose exec app alembic upgrade head
docker compose exec app python seed_db.py