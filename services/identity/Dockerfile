FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY libs/shared_kernel /libs/shared_kernel
RUN pip install --no-cache-dir -e "/libs/shared_kernel[dev]" 2>/dev/null || pip install --no-cache-dir -e /libs/shared_kernel \
    && pip install --no-cache-dir email-validator==2.2.0

COPY services/identity/app /app/app
COPY services/identity/migrations /app/migrations
COPY services/identity/alembic.ini /app/alembic.ini
COPY services/identity/tests /app/tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
