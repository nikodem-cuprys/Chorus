# Check that the llama.cpp server does not hang in the Linux container

Type: task (AFK)
Status: open
Blocked by: none

## Question

Ticket 11 starts llama.cpp's server once for the whole analysis stage, but build b11318 hung after one or two requests on Windows (ticket 08). Build llama.cpp for `sm_61` in a Linux container on the frozen stack (CUDA 12.x, driver R580, see the map's Notes), load Qwen3.5-4B with an 8k context on the 1050 Ti, and run the full approach B analysis of the six sample passages through the server (several hundred requests, including the blind second labelling run from ticket 18). Record: whether it hangs, speed against the Windows runs of ticket 08, and peak card memory. If it hangs, repeat with the Python binding (llama-cpp-python) and record the same. Resolves with those facts and a statement of which of the two the analysis stage uses.

## Comments

- 2026-10-03, not started: this machine cannot run a Linux container yet. Checked: Docker is not installed, WSL is not installed (only the `wsl.exe` stub that prints install help), and `systeminfo` reports "Virtualization Enabled In Firmware: No". The card and driver are fine (GTX 1050 Ti, driver 582.28). Needed from the user before this ticket can run: turn on SVM in the BIOS (AMD Ryzen 5 5600X), run `wsl --install` as administrator and reboot, then install Docker Desktop with the WSL2 backend and confirm `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi` shows the card. Windows 10 build 19045; ticket 05 notes Docker Desktop's Windows 10 support is ending. Left open and unclaimed; ticket 25 waits on the same thing.
