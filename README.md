# Сервис мониторинга строительных площадок (Backend)

Бэкенд-сервис и фоновый воркер видеоаналитики для автоматизированного контроля за объектами капитального строительства. Система сопоставляет видеопотоки со стройплощадок с утвержденным календарным планом, контролирует фактическое наличие техники на текущем этапе, фиксирует простои и выявляет регламентные отклонения.

---

## Ссылки на компоненты проекта

* **Репозиторий фронтенда:** [ссылка на фронтенд](https://github.com/Finolop/fruit-react)
* **Веса модели детекции (best.pt):** [ссылка на скачивание](https://drive.google.com/file/d/11dtAIx0FRrGh_5UiG5iteS2lJiVgfobn/view?usp=sharing)
* **Документация:** [ссылка на документ](https://docs.google.com/document/d/1FuQSR0WItCa34jEABzHTD657Uw9_gnBfRpuuE7bnzmg/edit?tab=t.0)
* **Презентация:** [ссылка на презентацию](https://drive.google.com/file/d/1obbHynODKZnOoBgMXJkox6DaHgzxYxGu/view)

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

```bash
docker compose up -d --build
```

### 3. Применение миграций и наполнение базы

Обязательный шаг при первом запуске:

```bash
docker compose exec app alembic upgrade head
docker compose exec app python seed_db.py
```

### 4. Запуск сквозных тестов (Опционально, создаст тестовый объект, который привяжет несуществующую камеру, чтобы удалить docker compose down -v)

```bash
docker compose exec app python test_all.py
```

---

## Доступ к сервисам

Swagger UI основного API: http://localhost:8000/docs
Эмулятор камеры (получение кадра): http://localhost:8081/frame.jpg
Swagger UI эмулятора: http://localhost:8081/docs

---

## Тестовые учетные записи

Скрипт seed_db.py создает учетные записи со следующими ролями:

| Роль | Email | Пароль | Полномочия |
| :--- | :--- | :--- | :--- |
| `Администратор (Департамент)` | admin@build.ru | admin12345 | Создание ОКС, назначение людей, сводный дашборд |
| `Инженер технадзора` | engineer@build.ru | engineer123 | Реакция на Red-алерты, каскадный сдвиг, штрафы |
| `Прораб` | foreman@build.ru | foreman123 | Редактирование плана в DRAFT, утверждение, старт этапов | 

## Работа с эмулятором камеры (MockServer)

Эмулятор используется для автономного тестирования видеоаналитики без подключения внешнего потока.

Исходные файлы кадров помещаются в директорию MockServer/dataset/ с именами по порядку (frame_01.png, frame_02.png и т.д.). Сервис отдает их по кругу.

При привязке камеры к объекту через API (POST /api/v1/projects/{project_id}/cameras) указывается внутренний адрес Docker-сети:

```
http://mock_camera:8081/frame.jpg
```

При отсутствии весов best.pt в корне проекта сервис автоматически переключается на встроенный режим симуляции детекций без прерывания пайплайна.

## Работа с моделью

Для работы воркера необходима модель, поместите в корневую папку проекта файл с весами, назвав его best.pt

## Полезные команды

Остановка контейнеров:

```bash
docker compose down
```

Остановка с полной очисткой базы данных:

```bash
docker compose down -v
```

Просмотр логов воркера сервиса:

```bash
docker compose logs -f service_name
```

Перезапуск эмулятора камеры (сброс отдачи кадров к первому):

```bash
docker compose restart mock_camera
```