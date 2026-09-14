FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/backend/src
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY contracts ./contracts
COPY backend ./backend
COPY knowledge_base ./knowledge_base
COPY models ./models
COPY docs ./docs
COPY evals ./evals
COPY scripts ./scripts
RUN pip install --no-cache-dir .
COPY --from=frontend /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "creditlens.main:app", "--host", "0.0.0.0", "--port", "8000"]
