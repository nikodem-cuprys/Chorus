#!/bin/sh
# llama-server with the CUDA runtime, cuBLAS and NCCL from the torch wheel (CUDA 12.6), and its
# backend libraries (libggml-cuda.so, the CPU variants) from /opt/llama.
NV=/opt/venv/lib/python3.12/site-packages/nvidia
export LD_LIBRARY_PATH="/opt/llama:$NV/cuda_runtime/lib:$NV/cublas/lib:$NV/nccl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec /opt/llama/llama-server "$@"
