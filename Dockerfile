# ---------- frontend builder stage ----------
FROM --platform=linux/amd64 node:22-alpine AS frontend-builder
WORKDIR /app

# Cache npm install layer separately from source
COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm ci --prefix frontend

# Copy everything else (templates + app templates needed for Tailwind content scanning)
COPY . .

# Build Tailwind CSS and Vite JS bundle
RUN mkdir -p static/css static/dist && \
    cd frontend && \
    npm run css:build && \
    npm run build

# ---------- builder stage ----------
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv \
    PATH="/venv/bin:$PATH"

# System deps for psycopg, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.4.29

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/venv \
    PATH="/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.local

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
      curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.4.29 \
    && groupadd --system app --gid 1000 \
    && useradd --system --gid app --uid 1000 --home /app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /venv /venv
COPY --chown=app:app . /app

# Bake frontend build outputs into the image (overrides empty gitignored dirs)
COPY --from=frontend-builder --chown=app:app /app/static/css /app/static/css
COPY --from=frontend-builder --chown=app:app /app/static/dist /app/static/dist

USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=6 \
  CMD curl -fsS http://localhost:8000/readyz/ || exit 1

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
