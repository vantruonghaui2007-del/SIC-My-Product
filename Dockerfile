FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MIXVERSE_DATA_DIR=/data/mixverse MIXVERSE_STATIC_DIR=/app/static
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend
COPY --from=web /app/frontend/dist /app/static
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/mixverse && chown -R appuser:appuser /data /app
USER appuser
EXPOSE 7860
CMD ["uvicorn", "mixverse.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "/app/backend"]
