# Chorus: from brief to build-ready spec

Label: wayfinder:map

## Destination

A build-ready spec for Chorus (in `docs/spec/`): product scope, architecture, the full pipeline from Source import to Published audio drama, chosen models and libraries each confirmed to run on a GTX 1050 Ti (4 GB), the data model, and milestones ready to split into build tickets.

## Notes

- **Domain:** see `CONTEXT.md` for the glossary (Source, Work, Speaker, Speaker attribution, Scene, Mood, Emotion, Script, Voice, Audio drama, Library, Publishing, YouTube export). Use these terms.
- **Skills:** grilling tickets call `grilling` + `domain-modeling`; prototype tickets call `prototype`; research tickets call `research`.
- **Standing constraints (from charting):**
  - Self-hosted, single user, used through a browser; shipped as Docker with NVIDIA GPU support, on Windows (WSL2) and Linux.
  - Local-first: the default pipeline runs fully offline on free/open models. Free cloud services only as optional plug-ins.
  - GTX 1050 Ti (4 GB, Pascal, compute capability 6.1) is the minimum for **every** stage, including text analysis. Slow is fine: no time limit.
  - English is required and tested first; the architecture must not block other languages (e.g. differing dialogue punctuation).
  - Audio drama = Narrator + distinct Character Voices with Emotion. No sound effects, no music.
  - Voices: auto-cast from a built-in set by character traits, the user can swap them, and zero-shot cloning from a user-supplied clip.
  - Review is optional: fully automatic by default; the user may fix any line afterwards and regenerate just that part.
  - Publishing: direct upload to YouTube only, and only as the final milestone; until then YouTube is reached through YouTube export. Everything else is local export (MP3/M4B with chapters).
  - Quality is judged by listening, not a formal benchmark.
  - Monetization may happen later: prefer commercially usable model licenses; clearly flag non-commercial ones.
  - Import: EPUB, MOBI, text-layer PDF, AO3 (by URL or by uploaded AO3 download, user's choice).
- **GPU stack is frozen (from research):** CUDA 12.x, `torch==2.14.0+cu126`, NVIDIA driver branch R580; llama.cpp built for `sm_61`. Compute in FP32 (Pascal FP16 is ~64x slower; half precision only to save memory). Budget ~2.8 GB usable VRAM when the host desktop shares the card. Only one model on the GPU at a time. Anything needing torch 2.15+, CUDA 13, vLLM, FlashAttention-2, bf16 or tensor cores is GPU-ineligible (CPU only).
- **Tracker quirk:** the repo had no commits at charting time, so research findings live in `.scratch/chorus/research/<name>.md` instead of `research/<name>` branches.

## Decisions so far

<!-- one line per closed ticket: - [<title>](issues/NN-slug.md): <gist> -->

- [Libraries for importing EPUB, MOBI, text PDFs and AO3 into one Work structure](issues/03-source-import-libraries.md): EPUB via our own reader on zipfile + lxml; MOBI/AZW3 via Calibre `ebook-convert` run as a separate process; PDF via pdfplumber + pypdf; AO3 "by URL" fetches the single work page (downloads are disallowed by robots.txt), and login-locked works go through upload. AGPL options (EbookLib, PyMuPDF) avoided.
- [Docker, GPU and PyTorch support for a Pascal card on WSL2](issues/05-docker-gpu-pascal-wsl2.md): works, but on a frozen stack (CUDA 12.x, torch 2.14.0+cu126, driver R580, base images pinned by digest); FP32 compute; ~2.8 GB usable VRAM with a desktop attached.
- [Free voice models that run on a 1050 Ti with emotion control and voice cloning](issues/01-tts-models-for-1050ti.md): no single model does it all; listening-test shortlist is Chatterbox 500M, IndexTTS-2 (offload/CPU), Qwen3-TTS 0.6B, Chatterbox-Nano. F5-TTS, XTTS-v2 and Fish Speech excluded as non-commercial.
- [Small local language models and tools for speaker attribution and emotion reading within 4 GB](issues/02-analysis-models-in-4gb.md): prototype (A) BookNLP + Qwen3.5-4B, (B) LLM-only chunked attribution with a global alias list (the multilingual path), (C) optional go_emotions baseline; the hard part is the character and alias list, and Mood can only be coarse.
- [YouTube upload API for a self-hosted single-user app](issues/04-youtube-upload-api.md): user brings their own Google Cloud project; uploads from unaudited projects are locked private, so an "Export for YouTube" path is also needed; one video per chapter plus a playlist per Work; synthetic-media disclosure on by default.
- [Collect a sample set of test passages from different kinds of books](issues/06-sample-passages.md): six public-domain passages (untagged dialogue, many Characters, first-person narrator, emotional shifts, quoted thoughts) plus import fixtures (clean EPUB, synthetic AO3-layout EPUB, synthetic hard PDF, AZW3, MOBI) in `samples/`.

- [How YouTube Publishing works given that unaudited uploads are locked private](issues/12-youtube-publishing-given-private-lock.md): YouTube export first (one video per chapter, cover with title text, upload checklist, AI-voice line in the description, pasted video links, "outdated" flags after regeneration); one-click Publishing with a status-and-statistics dashboard is the final milestone and never deletes old videos.
- [Listening test of the top voice candidates on the 1050 Ti](issues/07-voice-listening-test.md): default voice model is Chatterbox 500M (MIT, ~14x real time, `exaggeration` dial for Emotion); no fallback chosen. IndexTTS-2 came second but its Emotions are too aggressive and it runs ~65x real time; Chatterbox-Turbo shows no Emotion; Qwen3-TTS 0.6B was worst. Best Voice: young Jane (Kokoro `bf_isabella` reference); worst: the Narrator cloned from a LibriVox recording.
- [Re-run the chosen voice model on the frozen stack with a corrected memory measurement](issues/14-rerun-chosen-voice-model-on-frozen-stack.md): Chatterbox 500M runs on torch 2.14.0+cu126 (FP32, ~9x real time), so the frozen-stack note stands. It needs ~3.7 GB, not 2.8 GB: with a desktop on the card, ~3.4 GB sat on the card and ~1 GB spilled into Windows shared memory. The 2.8 GB budget in Notes does not hold for the voice stage.
- [Where the built-in Voice library comes from](issues/13-built-in-voice-library.md): 12 English Voices (6 women, 6 men, American and British, all adults), each one neutral clip rendered with Kokoro, prebuilt and bundled; labels are gender, age band, accent, timbre words and a Narrator flag. One fixed default Narrator Voice, never given to a Character; minor Characters share Voices; cloned Voices are used only when the user assigns them. Commercial-use sources only, credit acceptable.
- [Choose the 12 built-in Voices by listening](issues/15-choose-the-12-built-in-voices.md): the 12 Kokoro voices are af_alloy, af_aoede, af_bella, af_heart, af_kore, bf_emma, am_eric, am_fenrir, am_michael, bm_daniel, bm_fable, bm_lewis; default Narrator af_bella; fixed timbre word list of ten words. Clips and labels saved in `prototypes/voice-library/library/`.
- [Speaker attribution and emotion approach, judged on the sample passages](issues/08-attribution-approach-prototype.md): approach B, LLM-only chunked attribution with a global Character and alias list (Qwen3.5-4B, 8k context); 267 of 288 speakers right against 259 for BookNLP + LLM, and most misses are unclear in the text itself. BookNLP dropped, so no English-only attribution step. Emotion is often wrong and untuned; the review UI must make it easy to add or merge Characters, reassign runs of lines, change Emotion and merge Scenes.
- [How you review and correct the Script](issues/09-script-review-ux.md): the main screen is a reading view (the Work as prose, lines tinted by Speaker, cast beside it); review opens on a queue of the lines Chorus is unsure about. Corrections apply to one line, a selection, a Speaker's lines from here on, or all of them; corrected lines and Characters are pinned and survive a new analysis. Prototype in `prototypes/script-review/`.
- [Policy on permission to publish other authors' works and consent for cloned voices](issues/10-permissions-and-consent-policy.md): Chorus informs and never blocks. One warning ever about the author's permission at the first YouTube export or Publishing; no question when cloning a voice; an AO3 commercial-use line on every YouTube export and Publishing of an AO3 Work; the synthetic-content flag is on by default, switchable per Work, and forced on when a cloned Voice is not the user's own (asked once per Voice at Publishing); Chatterbox's watermark stays on by default with one global switch to turn it off; a short responsible-use note in the README.
- [Architecture and tech stack, including GPU sharing between the language and voice models](issues/11-architecture-and-stack.md): MIT; FastAPI backend, React + TypeScript frontend; PostgreSQL plus one FLAC file per line; Celery on Redis with a one-slot GPU queue and a second queue for everything else; each GPU stage is a child process that exits (analyse the whole Work, then voice it); llama.cpp server per analysis stage; engines behind interfaces; Docker Compose with web, worker, Redis and PostgreSQL from one Chorus image, models downloaded on first run; no login on localhost; server-sent events; a plain YouTube module.

## Not yet specified

- **llama.cpp server in the container:** ticket 11 runs llama.cpp's server for the whole analysis stage, but build b11318 hung after one or two requests on Windows (ticket 08). Still to check in the Linux container; the fallback is llama-cpp-python.

- **Which lines the review queue asks about:** the model gives no confidence score; four simple rules covered 14 of approach B's 21 wrong lines on the samples at the cost of 70 questions. Open: better rules, or a second model pass that scores its own doubt.
- **What a correction regenerates:** assumed, not confirmed: only lines whose Voice, Emotion, intensity or text changed are re-voiced, then the chapter is re-assembled. Also unconfirmed: in a first-person Work the Narrator uses the narrating Character's Voice.

- **Voice model memory:** Chatterbox 500M needs ~3.7 GB and only runs on a shared 1050 Ti by spilling into Windows system memory. The architecture (ticket 11) assumes it can be cut to fit. Still to measure in Docker/WSL2: half-precision weights with FP32 compute, and loading the model's two halves one at a time. If neither works, choose between accepting the spill (Linux has no such fallback) and requiring a card with no desktop on it.

- **YouTube dashboard:** what the final-milestone dashboard shows beyond upload status; which YouTube statistics, and the extra YouTube permission they need (not researched).
- **Library and player:** what the in-app Library holds and how listening works (progress, chapters, bookmarks, regeneration history).
- **Mood in delivery:** how Scene Mood becomes audible without music: narrator pacing, pauses, delivery style. Depends on what the chosen voice model can control. Research says scene boundaries are hard to detect, so Mood will be coarse.
- **Emotion label set:** the fixed list of Emotions a Script uses; should follow what the chosen voice model can express (settles after the listening test).
- **Pronunciation:** names and invented words (fantasy, fanfic); a per-Work pronunciation lexicon.
- **Voice consistency:** keeping a Character's Voice stable across a long Work and across regeneration; aliases and nicknames of one Character.
- **Special text:** AO3 author notes, italic inner thoughts, letters and text messages, footnotes, epigraphs, chapter titles.
- **Long jobs:** resume after a crash or reboot, progress reporting, and what "regenerate one line" means for already-assembled audio.
- **More languages:** how language-specific dialogue conventions and voice models plug in after English. Research: BookNLP is English-only, and a per-language quote splitter (em-dash dialogue, guillemets) must be built.
- **Milestones:** the build-order breakdown of the final spec.

## Out of scope

- Sound effects and background music or ambience: ruled out while charting; the audio drama is voices only.
- Spotify and podcast publishing: exported files only for now.
- OCR for scanned, image-only PDFs.
- Multiple users and hosted SaaS.
- DRM-protected files: rejected with a clear message, never decrypted (surfaced by [Libraries for importing EPUB, MOBI, text PDFs and AO3 into one Work structure](issues/03-source-import-libraries.md)).
- A formal accuracy benchmark: quality is judged by listening.
