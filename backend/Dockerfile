FROM python:3.12-slim

# ffmpeg: required for Gemini Native Audio, podcast generation, voice processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# uv binary — pin digest in production for fully reproducible builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer — rebuilt only when pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application source
COPY app/ app/

# Non-root user: Cloud Run security best practice
RUN useradd --system --no-create-home --uid 1001 appuser \
    && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Defaults match Settings; Cloud Run injects PORT at runtime
ENV HOST=0.0.0.0
ENV PORT=8080
ENV LOG_LEVEL=info

EXPOSE 8080

# exec ensures uvicorn receives SIGTERM directly (no shell wrapper in process tree)
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST} --port ${PORT} --log-level ${LOG_LEVEL}"]
