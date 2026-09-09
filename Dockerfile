FROM debian:trixie-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl libatomic1 \
 && rm -rf /var/lib/apt/lists/*

ENV MISE_DATA_DIR=/mise \
    MISE_CONFIG_DIR=/mise \
    MISE_CACHE_DIR=/mise/cache \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_TRUSTED_CONFIG_PATHS=/app \
    MISE_ENV=production \
    PATH=/mise/shims:$PATH \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN curl --proto '=https' --fail --silent --show-error --location \
      https://mise.run | sh

WORKDIR /app
COPY mise.toml mise.production.toml ./
RUN mise install

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev
