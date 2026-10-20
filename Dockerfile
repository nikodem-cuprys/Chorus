# The one Chorus image, run by both the `web` and `worker` services, on the frozen GPU stack:
# CUDA 12.6.3, Python 3.12, torch 2.14.0+cu126, llama.cpp b11318 built for sm_61
# (docs/spec/04-models-and-libraries.md). Base images are pinned by digest: NVIDIA deletes old
# CUDA tags from Docker Hub six months after their end of life.

ARG CUDA_BASE=nvidia/cuda:12.6.3-base-ubuntu24.04@sha256:c87e78933f4c16e3272123bf2f75537306596d0fbaa395a29696a22786e5ee0e
ARG CUDA_DEVEL=nvidia/cuda:12.6.3-devel-ubuntu24.04@sha256:392c0df7b577ecae17a17f6ba7f2009c217bb4422f8431c053ae9af61a8c148a
ARG NODE=node:24@sha256:3d27e5c11e5786e309ec3e03f93ae536eb36e6e5eb3714d5eb3300a36157add0
ARG NODE_SLIM=node:24-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20
ARG LLAMA_CPP_VERSION=b11318

# ---- The frontend ----
FROM ${NODE_SLIM} AS frontend
# Extra root certificates for hosts behind TLS-scanning antivirus or proxies (see certs/README.md).
COPY certs/ /certs/
RUN cat /certs/*.crt > /certs/extra.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/certs/extra.pem
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

# ---- llama.cpp's source, with the web UI its server embeds ----
FROM ${NODE} AS llama-source
ARG LLAMA_CPP_VERSION
COPY certs/ /usr/local/share/ca-certificates/chorus/
RUN update-ca-certificates
RUN cat /usr/local/share/ca-certificates/chorus/*.crt > /tmp/extra.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/tmp/extra.pem
RUN git clone --depth 1 --branch ${LLAMA_CPP_VERSION} https://github.com/ggml-org/llama.cpp /llama.cpp
WORKDIR /llama.cpp/tools/ui
RUN --mount=type=cache,target=/root/.npm npm ci && LLAMA_BUILD_NUMBER=${LLAMA_CPP_VERSION} npm run build

# ---- llama.cpp's server, built for the GTX 1050 Ti (sm_61) ----
# The same cmake options as llama.cpp's own .devops/cuda.Dockerfile, on CUDA 12.6.3 with
# Ubuntu 24.04's gcc 13 (CUDA 12.6's compiler rejects gcc 14, which that Dockerfile defaults to).
FROM ${CUDA_DEVEL} AS llama-build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git libssl-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=llama-source /llama.cpp /llama.cpp
WORKDIR /llama.cpp
RUN cmake -B build -DGGML_NATIVE=OFF -DGGML_CUDA=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON \
      -DLLAMA_BUILD_TESTS=OFF -DCMAKE_CUDA_ARCHITECTURES=61 \
      -DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined . \
    && cmake --build build --config Release -j"$(nproc)"
RUN mkdir -p /out \
    && find build -name "*.so*" -exec cp -P {} /out \; \
    && cp build/bin/llama-server /out/

# ---- The Chorus image ----
FROM ${CUDA_BASE}
# uv, as the GPU prototypes (tickets 24 and 25) were built with.
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
# Extra root certificates for hosts behind TLS-scanning antivirus or proxies (see certs/README.md).
COPY certs/ /usr/local/share/ca-certificates/chorus/
# Python 3.12 is Ubuntu 24.04's own. Calibre (ebook-convert) and ffmpeg run as separate
# programs; both are GPL, which makes the image an aggregate (docs/spec/04).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates python3 libgomp1 ffmpeg calibre \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    # On Linux, torch 2.14 JIT-compiles some operations with triton the first time they run,
    # which needs a C compiler; this switches that off (ticket 25).
    TORCH_DISABLE_NATIVE_JIT=1 \
    # Models come only from the First run's pinned download (chorus/firstrun.py), which does not
    # use huggingface_hub; the GPU code must never reach the network on its own.
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    # ebook-convert has no display in the container.
    QT_QPA_PLATFORM=offscreen \
    CHORUS_LLAMA_SERVER=/usr/local/bin/llama-server \
    CHORUS_FRONTEND_DIST=/app/frontend/dist

# The GPU stack first, so changing Chorus's own code does not reinstall torch.
COPY docker/requirements-gpu.txt docker/constraints-gpu.txt /tmp/gpu/
COPY backend/pyproject.toml /tmp/app/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv --python /usr/bin/python3 \
    && uv pip install --system-certs \
      -r /tmp/gpu/requirements-gpu.txt -r /tmp/app/pyproject.toml \
      --constraint /tmp/gpu/constraints-gpu.txt \
      --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match \
    && uv pip install --system-certs --no-deps chatterbox-tts==0.1.7

# llama-server uses the CUDA runtime and cuBLAS that come with the torch wheel, so the image
# needs no CUDA libraries of its own (the "base" flavour is enough).
COPY --from=llama-build /out/ /opt/llama/
COPY docker/llama-server.sh /usr/local/bin/llama-server
RUN chmod +x /usr/local/bin/llama-server

WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/chorus ./chorus
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system-certs --no-deps .
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY --from=frontend /src/frontend/dist /app/frontend/dist
EXPOSE 8000
