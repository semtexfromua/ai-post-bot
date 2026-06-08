# syntax=docker/dockerfile:1

#############################
# Builder: resolve + install deps with uv
#############################
FROM python:3.12-slim AS builder

# uv binary (pinned tag for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached layer): only lockfile + manifest.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project source and install the project itself.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

#############################
# Runtime: slim, non-root
#############################
FROM python:3.12-slim AS runtime

# Non-root user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Copy the resolved virtualenv and the application code from the builder.
COPY --from=builder --chown=app:app /app /app

# Make the venv the default interpreter; bytecode already compiled.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

# Default command runs the API; compose overrides for worker/beat/flower.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
