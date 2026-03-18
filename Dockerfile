FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       libpango-1.0-0 \
       libpangoft2-1.0-0 \
       libcairo2 \
       libgdk-pixbuf-2.0-0 \
       libgobject-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for reproducible locked installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY backend backend
COPY cli cli
COPY data data
COPY frontend frontend
COPY README.md .

# Install exact locked versions (no version drift)
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/healthz || exit 1

# Fix volume permissions at runtime (volume mounts as root after build)
# Fix volume permissions + clear corrupt WAL (DuckDB segfault recovery)
CMD ["sh", "-c", "chown -R appuser:appuser /app/data 2>/dev/null; rm -f /app/data/meridian.duckdb.wal; exec runuser -u appuser -- uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
