FROM python:3.12-slim

ARG SERVICE_VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SERVICE_VERSION

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gcc libnetcdf-dev \
    && pip3 install --no-cache-dir --upgrade pip uv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /worker
COPY pyproject.toml README.md LICENSE uv.lock ./
COPY src ./
COPY config ./config
COPY tests ./tests
RUN uv sync --frozen --extra dev --no-install-project
CMD ["uv", "run", "--no-sync", "pytest", "-m", "not integration"]
