FROM python:3.11-slim

WORKDIR /app

# Отключаем буферизацию логов и создание .pyc файлов
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Ставим curl для возможных проверок здоровья контейнера
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной проект
COPY . .

EXPOSE 8000

# Запуск с авто-перезагрузкой при изменении кода
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]