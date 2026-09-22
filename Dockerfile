# syntax=docker/dockerfile:1

ARG CUDA_VERSION=12.8.1
FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu24.04

ARG TORCH_SPEC=""
ARG TORCH_INDEX=""

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_PYTHON=3.12 \
    HF_HOME=/models \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-install-project --extra qwen

COPY jevall ./jevall
COPY scripts ./scripts
RUN uv sync --frozen --extra qwen

# The cu13 variant replaces the locked cu12 wheels with cu130 builds.
RUN if [ -n "${TORCH_SPEC}" ]; then \
        uv pip install --python /app/.venv/bin/python \
            --default-index https://pypi.org/simple \
            --index "${TORCH_INDEX}" \
            --index-strategy unsafe-best-match \
            ${TORCH_SPEC}; \
    fi

RUN mkdir -p /models

EXPOSE 8000
VOLUME ["/models"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

ENTRYPOINT ["serve"]
CMD ["--model", "demo"]
