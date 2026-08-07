FROM python:3.11-slim

# ffmpeg is a hard runtime dependency: audio extraction and chunking shell out
# to it. Everything else comes from pip.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# Coolify and most CI systems expose the commit being built. Passing it in
# lets the running app say which code it is instead of being guessed at.
ARG BUILD_COMMIT=unknown
ENV BUILD_COMMIT=${BUILD_COMMIT}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy the manifest first so dependency layers cache across code changes.
COPY pyproject.toml ./
COPY app ./app
# The postgres extra is included so one image serves both deployments: SQLite
# locally, PostgreSQL in production, chosen by DATABASE_URL alone.
RUN pip install --no-cache-dir ".[postgres]"

# Migration scripts are deployed, not installed: `app.cli migrate` reads them
# from disk, so a deployment can upgrade its schema before serving traffic.
COPY alembic.ini ./
COPY alembic ./alembic

RUN mkdir -p /data/work && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /data /app
USER appuser

ENV DATABASE_URL=sqlite+aiosqlite:////data/app.db \
    WORK_DIR=/data/work \
    # Whisper model cache. On the mounted volume so the ~150 MB download
    # survives a rebuild instead of happening again on every deploy.
    HF_HOME=/data/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
