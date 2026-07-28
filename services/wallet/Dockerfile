FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# A1 owns and packages the shared dependency layer.  The build context is the
# repository root, exactly as defined by the platform service template.
COPY libs/shared_kernel /libs/shared_kernel
RUN pip install --no-cache-dir -e /libs/shared_kernel

COPY services/wallet/app /app/app
COPY services/wallet/migrations /app/migrations
COPY services/wallet/alembic.ini /app/alembic.ini

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
