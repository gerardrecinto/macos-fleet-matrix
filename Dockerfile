# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && PIP_NO_CACHE_DIR=0 python -m pip wheel --no-deps --wheel-dir /dist .

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG VERSION=0.1.0

LABEL org.opencontainers.image.title="macos-fleet-matrix" \
      org.opencontainers.image.description="Ephemeral Apple Silicon macOS CI fleet control-plane reference implementation" \
      org.opencontainers.image.source="https://github.com/gerardrecinto/macos-fleet-matrix" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 mfm \
    && useradd --system --uid 10001 --gid 10001 --no-create-home mfm

COPY --from=builder /dist/*.whl /tmp/
RUN python -m pip install /tmp/*.whl \
    && rm -f /tmp/*.whl \
    && python -m compileall -q "$(python -c 'import site; print(site.getsitepackages()[0])')/mfm"

USER 10001:10001

ENTRYPOINT ["mfm"]
CMD ["--help"]
