# The one Chorus image, run by both the `web` and `worker` services.
# Ticket 02 moves the runtime stage onto the frozen CUDA stack and adds the GPU tools.

FROM node:24-slim AS frontend
# Extra root certificates for hosts behind TLS-scanning antivirus or proxies (see certs/README.md).
COPY certs/ /certs/
RUN cat /certs/*.crt > /certs/extra.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/certs/extra.pem
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
# uv, as the GPU prototypes (tickets 24 and 25) were built with.
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
# Extra root certificates for hosts behind TLS-scanning antivirus or proxies (see certs/README.md).
COPY certs/ /usr/local/share/ca-certificates/chorus/
RUN update-ca-certificates
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy \
    CHORUS_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/chorus ./chorus
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system --system-certs .
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY --from=frontend /src/frontend/dist /app/frontend/dist
EXPOSE 8000
