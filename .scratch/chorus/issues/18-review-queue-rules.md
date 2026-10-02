# Which lines the review queue asks about

Type: prototype
Status: open
Blocked by: none

## Question

The analysis model gives no confidence score. Ticket 09's four rules catch 14 of approach B's 21 wrong lines on the sample passages, at the cost of 70 questions. Try better rules and a second pass in which Qwen3.5-4B scores its own doubt per line, on the same sample Scripts (`../prototypes/attribution/`, `../prototypes/script-review/`). Resolves with the chosen way of picking queue lines, its catch rate and its number of questions on the samples.
