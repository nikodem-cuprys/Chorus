# Docker, GPU and PyTorch on a Pascal card (GTX 1050 Ti, sm_61) under WSL2 and Linux

Ticket: `issues/05-docker-gpu-pascal-wsl2.md`. Researched 2026-09-29.

## Short answer

Yes, it works, but only on a frozen CUDA 12.x stack. **CUDA 12.x is the last toolkit that can build Pascal kernels, NVIDIA driver branch R580 is the last driver that supports Pascal, and PyTorch 2.14 (cu126 wheels) is the last PyTorch that ships Pascal kernels.** Everything CUDA 13 (PyTorch cu128/cu130/cu132 wheels, llama.cpp `*-cuda13` images, default `onnxruntime-gpu` ≥ 1.27) has no sm_61 code and fails at runtime with "no kernel image is available for execution on the device".

## Pinned known-good version set

| Layer | Pin | Why |
|---|---|---|
| Host driver (Windows) | NVIDIA **R580 branch** (this machine: 582.28, WDDM, reports "CUDA 13.0"). Do not move to R590+. | R580 is the last branch with Pascal; LTS with security updates to Oct 2028 [N2][N3]. Runs CUDA 12.x apps by backward compatibility [N2]. |
| Host driver (Linux) | NVIDIA **580.x** (e.g. distro `nvidia-driver-580`). | Same [N2][N4]. |
| Windows | Windows 11 23H2+ (preferred) or Windows 10 22H2 (build 19045) | Docker Desktop WSL2 backend requirement [D2]. Windows 10 is only "supported while within Microsoft's servicing timeline" [D2]; see pitfalls. |
| WSL | WSL ≥ 2.1.5, kept current with `wsl --update` | [D1][D2] |
| Docker | Docker Desktop (WSL2 backend) on Windows; Docker Engine + NVIDIA Container Toolkit on Linux | [D1][N5] |
| Base image | `nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04` (runtime) and `nvidia/cuda:12.6.3-devel-ubuntu24.04` or `12.8.1-devel-ubuntu24.04` (build stage), **pinned by digest and mirrored** | EOL CUDA image tags are deleted from Docker Hub/NGC six months after EOL [N6]. |
| Python | 3.12 (Ubuntu 24.04 default) | cu126 wheels exist for cp310-cp315 [P5]. |
| PyTorch | **`torch==2.14.0+cu126`** from `https://download.pytorch.org/whl/cu126` | Last release with a CUDA 12 build; 2.15 removes cu126 [P3][P4]. |
| torchaudio | `torchaudio==2.11.0+cu126` | torchaudio is in maintenance; 2.11 is the final release and works with torch 2.11 and later [P6][P7]. |
| llama.cpp | Build from a pinned tag (latest seen: `b11256`) with `.devops/cuda.Dockerfile`, `CUDA_VERSION=12.8.1` (default) or `12.6.3`, and **`CUDA_DOCKER_ARCH=61`** | Default CUDA < 13 arch list only has `61-virtual` (PTX, JIT-compiled on first run); CUDA 13 drops 50/61/70 entirely [L1][L2][L3]. |
| CTranslate2 (if used) | 4.8.2 (CUDA 12 build), `compute_type="int8_float32"` or `float32` | Wheels built with CUDA 12.8 and `CUDA_ARCH_LIST=Common` [C1]; on CC 6.1 only `int8_float32` is native, everything else falls back to float32 [C2]. |
| ONNX Runtime (if used) | The CUDA 12 variant of `onnxruntime-gpu` 1.30.x, or the CPU EP | Default PyPI GPU packages ≥ 1.27 are CUDA 13 only [O1]. Whether the CUDA 12.8 packages contain sm_61 code is **not documented**, so test it with the smoke test. |

Minimum driver for the pins: cu126 needs ≥ 560.76 (Windows) / ≥ 560.28.03 (Linux), a CUDA 12.8 llama.cpp build needs ≥ 572.61 / ≥ 570.124.06 (12.8 Update 1) [N1]. R580 covers both. Ollama, if used, needs driver ≥ 570 for CC 5.0-6.2 and lists GTX 10-series as supported [OL1].

## Which versions still ship Pascal kernels

### NVIDIA CUDA toolkit and driver
- CUDA 12.8 declared Maxwell/Pascal/Volta "feature-complete"; **CUDA 13.0 removed offline compilation and library support** for them. NVIDIA's guidance for CC < 7.5: "remain on NVIDIA Driver branch 580 and CUDA Toolkit 12.9" [N2][N7].
- Current toolkit is 13.4 Update 1; the 13.x notes also drop pre-Turing from libraries such as cuSPARSE [N1].
- R580 is the final driver branch for pre-Turing GPUs, an LTS branch supported until mid-2028 [N2]; for GeForce, Game Ready updates ended Oct 2025 and quarterly security updates continue through Oct 2028 [N3].
- Apps built with an older toolkit keep running on newer drivers that still support the hardware [N2]. That is why an R580 driver that reports "CUDA 13.0" runs cu126 containers fine.

### PyTorch
- From 2.8, the cu128/cu129 builds dropped sm_50/sm_60 (Maxwell, Pascal) because of binary size; Pascal users must use **cu126** [P1][P2]. cu128 arch list: `7.5;8.0;8.6;9.0;10.0;12.0` [P2].
- cu126 arch list on Linux: `5.0;6.0;7.0;7.5;8.0;8.6;9.0` [P2]. There is no explicit `6.1`, but a cubin for compute capability X.y runs on X.z with z ≥ y [N8], so the sm_60 SASS runs on sm_61. Windows cu126 builds report `sm_61` explicitly [P8].
- 2.11 also removed Volta from cu128+ [P3]. From 2.11 the PyPI default is a CUDA 13 build, so **plain `pip install torch` gives a wheel that will not run on the 1050 Ti**. Always use the cu126 index URL.
- 2.14 matrix: CUDA 13.2 default, 13.0 stable, **12.6 legacy**. **2.15 removes CUDA 12.6**, which ends Maxwell/Pascal/Volta support; "Users on these GPUs should remain on PyTorch 2.14 (CUDA 12.6) or earlier" [P4][P9].
- `2.14.0+cu126` is published for Linux x86_64 and Windows, cp310-cp315 [P5].

### llama.cpp
- Default CUDA archs when `GGML_NATIVE=OFF`: with CUDA < 13, `50-virtual 61-virtual 70-virtual 75-virtual 80-virtual 86-real 89-real …`; with CUDA ≥ 13, the 50/61/70 entries are omitted [L1].
- The official Docker images come as `*-cuda` (CUDA 12.8.1 default) and `*-cuda13` variants. The docs say GPU images are "not currently tested by CI beyond being built" [L2][L3]. The official `server-cuda` image only has PTX for Pascal, so it works after a slow first-run JIT. A local build with `CUDA_DOCKER_ARCH=61` gives real sm_61 SASS.
- Release binaries: Windows CUDA 12.4 and 13.4; Ubuntu CUDA 12.8 and 13.4 [L4]. Only the 12.x ones can serve Pascal.

### Alternatives
- **CTranslate2**: viable. It is CUDA 12 only (no CUDA 13 build yet), and the wheels are built with CUDA 12.8, which can still target Pascal [C1]. Quantization matrix: CC 6.1 supports `int8_float32` natively and converts other types to float32 [C2]. Useful for faster-whisper-style ASR (for example, transcribing a user's cloning clip).
- **ONNX Runtime**: partly viable. 1.27-1.30 default to CUDA 13.0 packages, while separate CUDA 12.x packages are "built with CUDA 12.8 and require CUDA 12.8 or newer" [O1]. The page states no arch list. A community `onnxruntime-gpu-sm61` build exists [O2], which suggests official coverage is not guaranteed. The CPU EP is a safe fallback for small ONNX TTS models (Piper, Kokoro-ONNX).
- **Ollama**: officially supports CC 6.1 (GTX 1070/1080 Ti listed) with driver ≥ 570 [OL1].
- **Ruled out on Pascal** (first-party requirements): vLLM (needs CC ≥ 7.0) [V1], FlashAttention-2 (Ampere/Ada/Hopper only) [F1], and any wheel or image built only for CUDA 13.

## WSL2 pitfalls

1. **Do not install a Linux NVIDIA driver inside WSL.** The Windows driver is exposed as a stub `libcuda.so` under `/usr/lib/wsl/lib` [N5].
2. CUDA on WSL supports "Pascal and later" in WDDM mode [N5]. The 1050 Ti qualifies (confirmed WDDM on this machine).
3. Known limits from NVIDIA's WSL guide [N5]: no full Unified/managed memory, **limited pinned memory** (a problem for large DataLoader pinning or llama.cpp host buffers, so disable `pin_memory` if you hit errors), NVML utilization and process queries unavailable (`nvidia-smi` inside WSL shows less), and only `--gpus all` (no per-index selection).
4. **The display shares VRAM.** On this machine the 1050 Ti also drives the desktop and already uses about 1.26 GB of 4 GB at idle (`nvidia-smi`, 2026-09-29), leaving about 2.8 GB for models. Every VRAM budget in tickets 01/02 should assume about 2.5-2.8 GB on a Windows desktop machine, not 4 GB.
5. Docker Desktop support for Windows 10 is tied to Microsoft's servicing timeline [D2]. Windows 10 22H2 mainstream servicing ended Oct 2025, with consumer ESU only for one more year, so Windows 10 may stop being supported during the project. Windows 11 is the safer target. Docker Engine installed directly in WSL plus the NVIDIA Container Toolkit is an alternative that does not need Docker Desktop [MS1].
6. Windows 10 needs 21H2+ for WSL GPU compute [MS1] (this machine: 19045 = 22H2, OK).
7. Keep model and work files on the WSL/Docker filesystem (volumes), not bind mounts from `C:\`. Cross-OS file access is slow (general WSL guidance; not specific to GPU).
8. Verify GPU passthrough with `docker run --rm -it --gpus=all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark` [D1], then run the Chorus smoke test below.

## Pascal performance notes (affect model choice)

- CC 6.1 does FP16 arithmetic at a tiny fraction of the FP32 rate (programming-guide throughput table) [N8], and it has no tensor cores and no bf16. **Run PyTorch models in float32**. fp16/bf16 "speedups" do not apply, and fp32 doubles weight memory compared with fp16. That makes the 4 GB (in practice about 2.8 GB) budget tighter for TTS models.
- CTranslate2: use int8_float32 [C2]. llama.cpp: quantized GGUF (Q4_K_M etc.) uses its own MMQ/DP4A kernels, and CPU offload (`-ngl`) is fine.

## Smoke test to put in the image (build-time or first-run)

```python
import torch
assert torch.version.cuda.startswith("12."), torch.version.cuda
print(torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0), torch.cuda.get_arch_list())
x = torch.randn(1024, 1024, device="cuda"); print((x @ x).sum().item())  # fails with "no kernel image" on a cu128+/cu13 wheel
```
Also run `llama-server --version` and a 1-token generation with `-ngl 99`, plus `ctranslate2.get_cuda_device_count()` and an ORT `CUDAExecutionProvider` session if those libraries are used.

## Consequences for other tickets and the map

- **Freeze point:** the whole GPU stack is frozen at CUDA 12.x / torch ≤ 2.14 / driver R580 for the life of the 1050 Ti minimum. Any TTS or LLM candidate is **ruled out on GPU** if it hard-requires torch ≥ 2.15, a CUDA-13-only wheel, vLLM, FlashAttention-2, bf16, or tensor cores. Such candidates can still be judged on CPU fallback. Candidates pinning older torch (2.1-2.7 cu118/cu121/cu124) are fine, because those builds included Pascal.
- Ticket 01 (TTS): assume fp32 and about 2.8 GB usable VRAM on a Windows desktop machine. Flag candidates whose fast paths rely on vLLM or flash-attn (some CosyVoice/IndexTTS/Orpheus serving modes) and whose dependencies float to the latest torch.
- Ticket 02 (analysis LLM): llama.cpp and Ollama both work on Pascal. Use a llama.cpp CUDA 12 build with arch 61, never `*-cuda13` images.
- Ticket 11 (architecture): a single image with torch 2.14.0+cu126 plus a llama.cpp CUDA 12 build; pin base images by digest and mirror them. Driver R580 is a documented host prerequisite. Add the smoke test as a startup health check.
- Map note suggestion: "GPU stack frozen at CUDA 12.x, PyTorch 2.14.0+cu126, NVIDIA driver R580 (last Pascal branch, security updates to Oct 2028)."

## Sources

- [N1] NVIDIA CUDA Toolkit 13.4 Update 1 release notes (driver table, pre-Turing library drops): https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html
- [N2] NVIDIA Technical Blog, "Navigating GPU Architecture Support: A Guide for NVIDIA CUDA Developers": https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers
- [N3] NVIDIA support, "Support Plan for Maxwell, Pascal, and Volta-series GeForce GPUs": https://nvidia.custhelp.com/app/answers/detail/a_id/5676/
- [N4] Phoronix, "NVIDIA Confirms 580 Linux Driver Is The Last For Maxwell / Pascal / Volta" (reporting NVIDIA's Linux driver notice): https://www.phoronix.com/news/NVIDIA-580-Linux-Driver-Last-HW
- [N5] NVIDIA CUDA on WSL User Guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- [N6] NVIDIA CUDA container images support policy: https://gitlab.com/nvidia/container-images/cuda/-/blob/master/doc/support-policy.md
- [N7] CUDA Toolkit 13.0 release notes: https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html
- [N8] CUDA C++ Programming Guide (binary compatibility; arithmetic instruction throughput by CC): https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
- [P1] PyTorch dev-discuss, "Maxwell and Pascal architecture support removed in CUDA 12.8 and 12.9 builds" (2025-07-14): https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128
- [P2] pytorch/pytorch#157517 (arch lists per CUDA build): https://github.com/pytorch/pytorch/issues/157517
- [P3] PyTorch releases (2.8, 2.11 notes; 2.14.0 latest): https://github.com/pytorch/pytorch/releases
- [P4] pytorch/pytorch#190385, RFC CUDA support matrix for 2.15 (deprecate CUDA 12.6): https://github.com/pytorch/pytorch/issues/190385
- [P5] PyTorch cu126 wheel index: https://download.pytorch.org/whl/cu126/torch/
- [P6] torchaudio cu126 wheel index: https://download.pytorch.org/whl/cu126/torchaudio/
- [P7] torchaudio installation docs (2.11, stable ABI, maintenance): https://docs.pytorch.org/audio/stable/installation.html
- [P8] pytorch/pytorch#160575 (Windows 2.8.0+cu126 arch list includes sm_61): https://github.com/pytorch/pytorch/issues/160575
- [P9] PyTorch dev-discuss notice, CUDA 12.6 wheels not published from 2.15: https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432
- [L1] llama.cpp `ggml/src/ggml-cuda/CMakeLists.txt`: https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-cuda/CMakeLists.txt
- [L2] llama.cpp `.devops/cuda.Dockerfile`: https://github.com/ggml-org/llama.cpp/blob/master/.devops/cuda.Dockerfile
- [L3] llama.cpp Docker docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md (build docs: docs/build.md)
- [L4] llama.cpp releases: https://github.com/ggml-org/llama.cpp/releases
- [C1] CTranslate2 wheel build script: https://github.com/OpenNMT/CTranslate2/blob/master/python/tools/prepare_build_environment_linux.sh ; install docs: https://opennmt.net/CTranslate2/installation.html
- [C2] CTranslate2 quantization docs (compute type by CC): https://opennmt.net/CTranslate2/quantization.html
- [O1] ONNX Runtime CUDA Execution Provider requirements: https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html
- [O2] Community build `onnxruntime-gpu-sm61`: https://github.com/dmikushin/onnxruntime-gpu-sm61
- [OL1] Ollama GPU docs: https://docs.ollama.com/gpu
- [D1] Docker Desktop GPU support: https://docs.docker.com/desktop/features/gpu/
- [D2] Docker Desktop Windows install requirements: https://docs.docker.com/desktop/setup/install/windows-install/
- [MS1] Microsoft Learn, GPU accelerated ML training in WSL: https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute
- [V1] vLLM GPU installation requirements (compute capability 7.0+): https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html
- [F1] FlashAttention README (FA2 supports Ampere, Ada, Hopper): https://github.com/Dao-AILab/flash-attention
- Local check: `nvidia-smi` on the target machine, 2026-09-29: GTX 1050 Ti, driver 582.28, WDDM, 1257 MiB / 4096 MiB in use at idle.

Not verified from a primary source: whether the ONNX Runtime CUDA 12.8 packages include sm_61 code, and the exact CMake "Common" arch list CTranslate2 resolves under CUDA 12.8. Both are covered by the smoke test. vLLM [V1] and FlashAttention [F1] are cited from their docs as known, not re-fetched today.
