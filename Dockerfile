# ── Stage 1: Build Frontend Widget & Showcase Landing Page ──────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/widget

# Copy widget package manifests and install dependencies
COPY widget/package*.json ./
RUN npm install --no-audit

# Copy widget source and config files
COPY widget/ ./

# Build widget.min.js and generate production dist/index.html
RUN npm run build

# ── Stage 2: Production Python Runtime ────────────────────────────────
FROM python:3.12-slim AS runner

# Optimize Python execution and configure default Render port
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

# Install required system packages for audio, voice models (Whisper/Kokoro), and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements and install dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend ./backend

# Copy compiled frontend assets from Stage 1 into widget/dist
COPY --from=frontend-builder /app/widget/dist ./widget/dist

# Expose Render service port
EXPOSE 10000

# Health check verifies the FastAPI gateway is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start the FastAPI gateway with Uvicorn
WORKDIR /app/backend
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
