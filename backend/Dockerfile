# Backend API image. Build context = repo root (needs src/ and data/ too):
#   docker build -f backend/Dockerfile -t jobhunt-api .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching.
COPY backend/requirements.txt backend/requirements-pipeline.txt ./backend/
RUN pip install -r backend/requirements.txt -r backend/requirements-pipeline.txt \
        "psycopg[binary]"

# App code + the pipeline it wraps + the non-personal data files it reads.
COPY src ./src
COPY data ./data
COPY backend ./backend

WORKDIR /app/backend
EXPOSE 8000

# Run migrations, then serve (single process so the in-app scheduler runs once).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
