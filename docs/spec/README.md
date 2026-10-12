# Chorus: build spec

Chorus turns a written work into a multi-voice audio drama with emotional delivery, keeps it in a personal Library, exports it as audio files and YouTube-ready videos, and finally Publishes it to YouTube. It is self-hosted, used by one person through a browser, and runs offline on free models on a GTX 1050 Ti (4 GB).

This spec is written from the decisions of the wayfinding tickets in `.scratch/chorus/issues/` (01 to 29), summarised in `.scratch/chorus/map.md`. Where a later ticket changed an earlier one, only the later decision is stated. The terms are those of [`CONTEXT.md`](../../CONTEXT.md); read it first.

## Parts

| File | What it covers |
|---|---|
| [01-scope.md](01-scope.md) | What Chorus does and does not do, and the standing constraints |
| [02-architecture.md](02-architecture.md) | Stack, services, jobs, GPU turn-taking, storage, access, licence |
| [03-pipeline.md](03-pipeline.md) | Every stage from Source import to Publishing, in order |
| [04-models-and-libraries.md](04-models-and-libraries.md) | Chosen models, libraries and pinned versions, with licences and measurements |
| [05-data-model.md](05-data-model.md) | What is stored, and how a correction, a new analysis and a re-voicing touch it |
| [06-screens.md](06-screens.md) | Every screen and what it shows |
| [07-milestones.md](07-milestones.md) | The nine milestones, ready to split into build tickets |
| [08-open-questions.md](08-open-questions.md) | Things found undecided while writing, and known risks |

## Evidence kept outside the spec

- Sample passages and import fixtures: `.scratch/chorus/samples/` (index in its `README.md`).
- Built-in Voice clips and labels: `.scratch/chorus/prototypes/voice-library/library/` (`voices.json` and 12 clips). These ship with Chorus.
- Emotion settings for Chatterbox 500M: `.scratch/chorus/prototypes/emotion-settings/emotions.json`. These ship with Chorus.
- Prototypes of attribution, the review queue, the review screen and the voice-model fit: `.scratch/chorus/prototypes/`. They are throwaway code: read them for what was measured, not as a starting point.
- Research notes with sources: `.scratch/chorus/research/`.

## Where each decision lives

Every line of the map's "Decisions so far" is reflected here.

| Ticket | Decision | Spec section |
|---|---|---|
| 01 | Voice model candidates and licence exclusions | 04 Voice model |
| 02 | Analysis model and approaches | 04 Analysis model |
| 03 | Import libraries, shared Work structure, AO3 rules | 03 Import, 04 Import libraries |
| 04 | YouTube API: own Cloud project, private lock, quota, layout | 03 Publishing, 08 |
| 05 | Frozen GPU stack, FP32, Docker on WSL2 | 02 Docker, 04 Pinned stack |
| 06 | Sample passages and fixtures | README, 07 test data |
| 07 | Chatterbox 500M chosen by ear | 04 Voice model |
| 08 | Approach B for Speaker attribution; failure cases | 03 Analysis, 06 Reading view |
| 09 | Reading view plus question queue; correction scopes; pinning | 06 Reading view, 05 Corrections |
| 10 | Permissions and consent: inform, never block | 03 YouTube export and Publishing, 06 |
| 11 | Architecture and stack | 02 |
| 12 | YouTube export first; Publishing last | 03, 06, 07 |
| 13 | Built-in Voice library and casting rules | 03 Casting, 05 Voice |
| 14 | Chatterbox memory on the frozen stack | 04 Measurements |
| 15 | The 12 built-in Voices and the default Narrator | 04 Built-in Voices |
| 16 | Nine Emotions, two intensities, seed per line | 03 Voicing, 04 Emotion settings |
| 17 | No Mood; neutral Narrator; fixed pauses | 03 Voicing and assembly |
| 18 | Review queue rules and the second labelling run | 03 Analysis, 06 Question queue |
| 19 | Pronunciation list and Respellings | 03 Voicing, 06 Pronunciation panel |
| 20 | What a correction re-voices; Narrating Character; job control | 03 Regenerate, 02 Jobs, 05 |
| 21 | Special kinds of text | 03 Analysis, 05 Work switches |
| 22 | Library, Work page, player, previous take, Update from Source | 06, 03 Update from Source |
| 23 | YouTube statistics and scopes | 03 Publishing |
| 24 | llama.cpp server in the container | 04 Analysis model |
| 25 | Chatterbox's two halves loaded in turn | 03 Voicing, 04 Measurements |
| 26 | Scenes dropped; Section break only | 03, 05, 06 |
| 27 | YouTube dashboard contents | 06 YouTube page |
| 28 | Language packs; message catalogue | 02 Language packs, 03 Import |
| 29 | Milestones | 07 |
