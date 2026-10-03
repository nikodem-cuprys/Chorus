# Fit Chatterbox 500M on a shared 1050 Ti in Docker

Type: task (AFK)
Status: open
Blocked by: none

## Question

Chatterbox 500M needs about 3.7 GB and ran on a shared 1050 Ti only by spilling about 1 GB into Windows shared memory (ticket 14). Ticket 11 assumes it can be cut to fit. In Docker on WSL2, on the frozen stack, measure the two ideas from ticket 11 on the eight lines of ticket 14: weights stored in half precision with FP32 compute, and loading the model's two halves one at a time. For each, and for both together, record: whether it runs, peak card memory, any spill into system memory, speed, and whether the audio is the same by ear as the ticket 14 clips for the same seed. Also record what happens in the container with no change: does the spill still work under WSL2, and what would happen on Linux, which has no such fallback. Resolves with those facts and one of: the setting Chorus uses, or a statement that neither works, which reopens the voice memory decision of ticket 11 (accept the spill, or require a card with no desktop on it).

## Comments

- 2026-10-03: waits on the same machine setup as ticket 24 (virtualization off in the BIOS, no WSL2, no Docker). See the comment there.
