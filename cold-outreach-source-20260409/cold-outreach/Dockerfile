# ── Stage 1: build frontend (latest UI) ───────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Cloud Run serves frontend + API at the same origin → use relative /api.
# Drop .env.production so VITE_API_URL is unset (otherwise it bakes in an absolute URL).
RUN rm -f .env.production .env.local && npm run build

# ── Stage 2: backend + bundled frontend ───────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libxshmfence1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY backend/ ./

# Clean up any stale static assets that came from the copy of the backend directory
RUN rm -rf ./static

# Replace any stale bundled frontend with the freshly built one
COPY --from=frontend /fe/dist ./static

EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
