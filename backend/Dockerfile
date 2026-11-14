FROM node:22-bookworm-slim AS signer
WORKDIR /signer
COPY signer/package*.json ./
RUN npm ci --omit=dev

FROM rust:1.95.0-slim-bookworm AS renderer
WORKDIR /renderer
COPY contracts/onchain-art/src/renderer.rs src/renderer.rs
COPY contracts/onchain-art/examples/render_recipe.rs examples/render_recipe.rs
RUN rustc --edition=2021 -O examples/render_recipe.rs -o /render_recipe

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /uvx /bin/
COPY --from=signer /usr/local/bin/node /usr/local/bin/node
COPY --from=renderer /render_recipe /usr/local/bin/intent-render-recipe
WORKDIR /app
ENV ECHOES_ROOT=/app UV_PROJECT_ENVIRONMENT=/app/.venv UV_PYTHON_DOWNLOADS=never
ENV ONCHAIN_RENDERER_BINARY=/usr/local/bin/intent-render-recipe
COPY pyproject.toml uv.lock .python-version ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/app backend/app
RUN uv sync --locked --no-dev --no-editable
COPY --from=signer /signer/node_modules signer/node_modules
COPY signer/sign.mjs signer/sign.mjs
COPY backend/alembic backend/alembic
COPY backend/alembic.ini backend/alembic.ini
COPY scripts scripts
COPY fixtures/collection fixtures/collection
RUN useradd -m echoes && mkdir -p /app/data && chown -R echoes:echoes /app
USER echoes
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
