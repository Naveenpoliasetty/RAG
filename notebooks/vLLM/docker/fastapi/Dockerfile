FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn requests slowapi httpx prometheus_client

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
