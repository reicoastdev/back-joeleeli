# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN addgroup --system django && adduser --system --ingroup django django

COPY pyproject.toml uv.lock ./

FROM base AS development
RUN uv sync --frozen --no-install-project
COPY --chown=django:django . .
USER django
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production
RUN uv sync --frozen --no-dev --no-install-project
COPY --chown=django:django . .
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY=collectstatic-build-only-not-a-runtime-secret \
    DATABASE_URL=postgresql://build:build@localhost:5432/build \
    DJANGO_ALLOWED_HOSTS=localhost \
    uv run --no-sync python manage.py collectstatic --noinput
USER django
EXPOSE 8000
CMD ["sh", "-c", "exec uv run --no-sync gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
