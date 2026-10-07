# How a second language plugs in after English

Type: grilling
Status: resolved
Blocked by: none

## Question

English is required and tested first, and the architecture must not block other languages. What is fixed so far: attribution is LLM-only with no English-only step (ticket 08); engines sit behind interfaces (ticket 11); the 12 built-in Voices are English and rendered with Kokoro (tickets 13 and 15); the review queue has five text rules (ticket 18); dialogue punctuation differs by language (em-dash dialogue, guillemets). Decide what the first build must contain so that a second language is an addition and not a rewrite: where a Work's language is recorded and how it is detected; which parts are per-language (dialogue splitting, the queue's text rules, the candidate list for Respellings, the built-in Voices and their labels, the voice model); what Chorus does today with a Work in another language (refuse, warn, or try); and whether the interface text itself is translatable. Naming the second language and testing it are out of scope here.

## Answer

Chosen by the user on 2026-10-05, in a grilling session.

**The Work's language**

- **Recorded:** one language per Work, as a plain code such as `en` or `pl`. Regional variants (`en-GB`) count as the base language. There is no language per chapter or per line; a foreign phrase inside a Work is read by that Work's voice model.
- **Detected:** from the Source's metadata when it states a language (EPUB and AO3 do), otherwise by a small offline language detector run on the text. It is shown on the Work page, where the user can change it. Which detector library is left to the build.
- **Changed later:** nothing runs by itself. The Script and the audio are flagged outdated, the user starts a new analysis when ready, pinned corrections survive (ticket 09), and Voices are cast again from the new language's set.

**Language packs**

Everything that differs by language sits in one Language pack per language. English is the first pack and the only one in the first build. A Work's language picks the pack. A second language is a new pack plus its test.

| Part | Required | Without it |
|---|---|---|
| Quotation rules for the dialogue splitter (which mark pairs open and close speech, whether a leading dash starts dialogue) | yes | |
| The voice model | yes | |
| Built-in Voices with a default Narrator, same labels as ticket 13 | yes | |
| Speech-verb list for the queue's "said X" rule (ticket 18) | no | the rule is skipped; the other four rules and the second run still work |
| Dictionary for Respelling candidates (ticket 19) | no | only Character names are offered as candidates |
| Listener-facing export lines (the AI-voice line, the AO3 commercial-use line) | no | the English lines are used |

- **Dialogue splitting:** rule-based, with the rules taken from the pack. Not detected from the text and not done by the analysis model.
- **Voice model:** per language, loaded through the engine interface of ticket 11, and chosen by listening when that language is added. English stays on Chatterbox 500M. The Emotion settings of ticket 16 are therefore stored per voice model, not globally.
- **Voices:** each language brings its own built-in set. Auto-casting only draws from Voices of the Work's language.
- **Analysis prompts:** always English, for every Work; only the passage is in the Work's language. Emotion names are internal English ids, translated only in the interface. Packs carry no prompts.

**A Work in a language without a pack**

Warn, then try. The Work imports, its page shows a notice that the language is not supported and that the English pack will be used (English quotation rules, voice model and Voices), and the user may run it anyway. Setting the Work's language to English by hand removes the notice. No confirmation per job.

**Interface text**

- Every interface string goes through a message catalogue from the first build, shipped in English and Polish. That includes Emotion names, Voice labels and timbre words, warnings and job messages.
- A test fails when a string exists in one language and not in the other.
- The interface follows the browser's language on first use; a remembered setting overrides it; any other language falls back to English.
- Text meant for listeners (the export lines above, the cover's title text) follows the Work's language. The upload checklist, which only the user reads, follows the interface language.

**Not settled here:** the second language itself and its voice model (out of scope by the ticket); the detector library; whether Chatterbox 500M is English-only and its multilingual sibling a separate model was stated from memory and not checked. Tickets 18 and 19 are not edited; the spec states the per-language reading.
