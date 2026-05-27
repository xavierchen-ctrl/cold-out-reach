# Stage 1: build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# System deps for psycopg2 + Playwright Chromium
RUN apt-get update && apt-get install -y \
    gcc libpq-dev \
    # Playwright Chromium dependencies
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libxshmfence1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install only Chromium (no extra fonts/deps that may not exist)
RUN playwright install chromium

COPY backend/ ./
COPY --from=frontend-builder /frontend/dist ./static

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
