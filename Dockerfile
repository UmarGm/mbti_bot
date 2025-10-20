FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Системные пакеты для сборки Python-зависимостей (gcc и др.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ставим зависимости отдельно для лучшего кеша
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# Копируем код
COPY . .

# Healthcheck для Koyeb (проверяет наш Flask-наблюдатель)
HEALTHCHECK --interval=10s --timeout=2s --retries=5 CMD curl -fsS http://127.0.0.1:${PORT}/ || exit 1

# Поднимаем health-сервер и бота
CMD bash -lc "python -m app.health & exec python -m app.bot"
