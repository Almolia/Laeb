FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.12 httpx==0.28.1 uvicorn==0.34.2
COPY mock-psp/app.py ./app.py
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
