# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + static files ────────────────────────────────────
FROM python:3.12-slim AS final

WORKDIR /app

# System deps for ReportLab (freetype for TTF fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./backend/

# Frontend build output → servido por FastAPI como static files
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Cloud Run inyecta PORT; uvicorn lo usa
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
