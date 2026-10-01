# Docker, GPU and PyTorch support for a Pascal card on WSL2

Type: research
Status: resolved
Blocked by: none

## Question

Can a Docker image with NVIDIA GPU access run PyTorch and llama.cpp on a GTX 1050 Ti (Pascal, sm_61) under Docker Desktop with WSL2 on Windows 10/11, and on native Linux? Specifically: which CUDA and PyTorch versions still ship sm_61 kernels (recent CUDA 12.8+/13 builds may drop Pascal), which driver versions are required, known pitfalls of GPU passthrough on WSL2, and whether ONNX Runtime or CTranslate2 are viable alternatives. Deliver a pinned, known-good set of versions.

## Answer

Yes, on a frozen CUDA 12 stack. Pascal support ends with CUDA 12.x (13.0 removed it), NVIDIA driver branch R580 (LTS, security updates to Oct 2028) and PyTorch 2.14 (`torch==2.14.0+cu126`; 2.15 drops cu126).
Pins: R580 host driver, `nvidia/cuda:12.6.3` base images pinned by digest, Python 3.12, torch 2.14.0+cu126, torchaudio 2.11.0, llama.cpp built with CUDA 12.8.1 and `CUDA_DOCKER_ARCH=61` (never `*-cuda13`). CTranslate2 4.8.2 works (int8_float32). ONNX Runtime needs the CUDA 12 package or the CPU EP.
WSL2: no Linux driver in WSL, limited pinned and unified memory, and the desktop takes about 1.3 GB of the 4 GB of VRAM. Windows 10 support in Docker Desktop is ending. Run models in fp32 (Pascal FP16 is very slow). vLLM and FlashAttention-2 are ruled out.
Full findings: [research/docker-gpu-pascal-wsl2.md](../research/docker-gpu-pascal-wsl2.md)
