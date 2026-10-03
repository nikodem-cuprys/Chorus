# How a second language plugs in after English

Type: grilling
Status: open
Blocked by: none

## Question

English is required and tested first, and the architecture must not block other languages. What is fixed so far: attribution is LLM-only with no English-only step (ticket 08); engines sit behind interfaces (ticket 11); the 12 built-in Voices are English and rendered with Kokoro (tickets 13 and 15); the review queue has five text rules (ticket 18); dialogue punctuation differs by language (em-dash dialogue, guillemets). Decide what the first build must contain so that a second language is an addition and not a rewrite: where a Work's language is recorded and how it is detected; which parts are per-language (dialogue splitting, the queue's text rules, the candidate list for Respellings, the built-in Voices and their labels, the voice model); what Chorus does today with a Work in another language (refuse, warn, or try); and whether the interface text itself is translatable. Naming the second language and testing it are out of scope here.
