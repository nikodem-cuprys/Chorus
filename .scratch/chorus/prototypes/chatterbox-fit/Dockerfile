# PROTOTYPE, throwaway (ticket 25). Chatterbox 500M on the frozen stack: CUDA 12.6.3, Python 3.12, torch 2.14.0+cu126.
# Build from the prototypes folder: docker build -t chorus-chatterbox-fit -f chatterbox-fit/Dockerfile voice-listening-test
# The base image is the "base" flavour, not "cudnn-runtime": the torch wheel brings its own CUDA and cuDNN libraries.
FROM nvidia/cuda:12.6.3-base-ubuntu24.04
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
COPY constraints-frozen.txt overrides-frozen.txt /tmp/
# the cache mount keeps finished downloads, so a build that fails on a slow connection resumes where it stopped
ENV UV_HTTP_TIMEOUT=600 UV_HTTP_RETRIES=10 UV_CONCURRENT_DOWNLOADS=4 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv uv venv /opt/venv --python /usr/bin/python3 && \
    uv pip install --python /opt/venv/bin/python \
      torch torchaudio chatterbox-tts soundfile setuptools \
      --constraint /tmp/constraints-frozen.txt --override /tmp/overrides-frozen.txt \
      --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
# torch 2.14 on Linux JIT-compiles some operations with triton, which needs a C compiler; switch that off
ENV PATH=/opt/venv/bin:$PATH HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1 TORCH_DISABLE_NATIVE_JIT=1
WORKDIR /work
