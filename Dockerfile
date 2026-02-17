FROM node:22-alpine AS web-builder
WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY api.py ./
COPY art_finder/ ./art_finder/
COPY --from=web-builder /build/web/dist ./web/dist

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080}"]
