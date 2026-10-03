# Check that the llama.cpp server does not hang in the Linux container

Type: task (AFK)
Status: open
Blocked by: none

## Question

Ticket 11 starts llama.cpp's server once for the whole analysis stage, but build b11318 hung after one or two requests on Windows (ticket 08). Build llama.cpp for `sm_61` in a Linux container on the frozen stack (CUDA 12.x, driver R580, see the map's Notes), load Qwen3.5-4B with an 8k context on the 1050 Ti, and run the full approach B analysis of the six sample passages through the server (several hundred requests, including the blind second labelling run from ticket 18). Record: whether it hangs, speed against the Windows runs of ticket 08, and peak card memory. If it hangs, repeat with the Python binding (llama-cpp-python) and record the same. Resolves with those facts and a statement of which of the two the analysis stage uses.
