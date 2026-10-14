# Architecture

## Stack

- **Licence:** MIT. Nothing AGPL or GPL is imported into Chorus's own processes. GPL programs (Calibre) run as separate processes, which makes the image an aggregate.
- **Backend:** Python 3.12 on FastAPI, with a JSON API. SQLAlchemy and Alembic migrations.
- **Frontend:** React and TypeScript, built with Vite and served by the backend.
- **Repository:** one repository with `backend/` and `frontend/` folders.
- **Progress to the browser:** server-sent events.

## Services

Docker Compose with four services:

| Service | Runs |
|---|---|
| `web` | The FastAPI app and the built frontend |
| `worker` | Celery workers for both queues, and the GPU child processes |
| `redis` | Celery's broker |
| `postgres` | PostgreSQL |

`web` and `worker` run the same Chorus image. It contains Python, the CUDA 12 runtime libraries that come with the torch wheel, PyTorch, llama.cpp's server built for `sm_61`, ffmpeg and Calibre. It does not contain models.

Volumes:

| Volume | Holds |
|---|---|
| data | Source copies, line audio (FLAC), assembled chapter audio, covers |
| models | Model weights, downloaded on first run |
| postgres | The database |
| exports (a host folder bind-mounted) | MP3, M4B and YouTube exports, one sub-folder per Work, so they are ordinary files on the host |

The image sets `TORCH_DISABLE_NATIVE_JIT=1`. On Linux, torch 2.14 otherwise compiles some kernels with triton the first time they run, which needs a C compiler that the image does not have.

**First run:** models are downloaded in pinned versions into the models volume, with progress shown in the browser. Nothing else can run until they are in place. A startup health check runs a small CUDA matrix multiply through torch and a one-token generation through llama.cpp, so a wrong wheel or driver fails loudly ("no kernel image is available").

**Host prerequisites,** documented in the README: NVIDIA driver branch R580 (the last with Pascal support; security updates until October 2028); on Windows, WSL2 and Docker Desktop with the WSL2 backend, without a Linux NVIDIA driver inside WSL; on Linux, Docker Engine and the NVIDIA Container Toolkit. Windows 10 support in Docker Desktop is ending; Windows 11 is the safer host.

## Jobs

Celery on Redis, with two queues:

| Queue | Slots | Jobs |
|---|---|---|
| GPU | 1 | Analysis, voicing, re-voicing, "try it" for a Respelling |
| Other | several | Import, chapter assembly, MP3/M4B export, YouTube export, YouTube upload and statistics |

So import, assembly and export run while audio is being generated.

- **Saved as it goes:** every finished analysis chunk and every voiced line is saved at once. A job that stops continues where it stopped.
- **Controls:** pause, resume and cancel for analysis, voicing and export. Pause stops after the current line or chunk and frees the GPU. Cancel keeps every finished line, so starting again does only what is missing; throwing audio away is a separate, explicit action.
- **After a crash or reboot:** a running job resumes by itself when Chorus is back up; a paused job stays paused.
- **Progress:** the stage, chapter x of y, lines done of total, a percentage and a time-left estimate from the measured speed. Shown on the Work page and in the Library.
- **Corrections never restart a running job** (see [03-pipeline.md](03-pipeline.md#regenerate)).

## GPU turn-taking

Only one model is on the card at a time, and the card is often shared with the desktop.

- Each GPU stage runs as its own child process that exits when it is done, which guarantees the card's memory is free afterwards.
- A Work is analysed in full first, then voiced.
- **Analysis:** llama.cpp's server is started at the beginning of the stage, with one slot (`-np 1`) and 8k context, and stopped at the end, so the model loads once.
- **Voicing:** Chatterbox 500M is loaded in two halves, one at a time. T3 (text to speech tokens) runs over a batch of lines, leaves the card, then S3Gen (speech tokens to audio) runs over the same batch. A batch is a chapter, or the lines waiting for Regenerate. Swapping takes about a second, so re-voicing a single line pays that each time.
- Compute is always FP32. Pascal's FP16 arithmetic is about 64 times slower, so half precision is only ever a way to store weights.

Measured peaks on the card are in [04-models-and-libraries.md](04-models-and-libraries.md#measurements). The old 2.8 GB budget does not hold for analysis (3.3 GB added at peak); voicing with the split adds 2.5 GB.

## Engines

The analysis model and the voice model each sit behind an interface, with one implementation each: Qwen3.5-4B through the llama.cpp server, and Chatterbox 500M. The voice-model interface is chosen per Language pack. The Emotion settings belong to a voice model, not to Chorus as a whole.

## Storage

- **PostgreSQL** holds Works, chapters, the Script (lines and Characters with aliases), Voices, the pronunciation lists, bookmarks, jobs, exports, settings and the YouTube records. See [05-data-model.md](05-data-model.md).
- **Audio:** one FLAC file per line on the data volume. Each line keeps its current take and the one before it; older takes are deleted. Chapter audio for the player and the MP3/M4B exports are assembled from the line files with ffmpeg and cached. Any change to a chapter's lines or pauses re-assembles that chapter.

## Access

- No login. The port is published on localhost only by default.
- Opening Chorus to the home network requires setting a single password (milestone 5).
- The YouTube Connect step must happen in a browser on the Docker host at `http://localhost:<port>`, because Google only allows localhost or HTTPS redirects. After that, the stored refresh token works from anywhere.

## YouTube module

One plain backend module, with no general Publishing plug-in interface. It holds the YouTube export (milestone 8) and the Connect wizard, upload and statistics (milestone 9). Uploads and statistics run on the non-GPU queue. Google client secrets and tokens are stored encrypted in the database.

## Language packs

Everything that differs by language sits in one Language pack per language. A Work's language picks its pack. English is the only pack in the first build; a second language is a new pack plus its test.

| Part of a pack | Required | Without it |
|---|---|---|
| Quotation rules for the line splitter: which mark pairs open and close speech, alternative pairs for Works that quote with them (‘ ’), and whether a leading dash starts dialogue | yes | |
| How the Work title and author line is said ("{title}, by {authors}") | no | the title alone |
| Sentence rules for splitting long lines before voicing: sentence-end punctuation and an abbreviation list ("Mr.", "Mrs.", "Dr.", "St.") | yes | |
| The voice model, with its Emotion settings | yes | |
| Built-in Voices with a default Narrator, labelled as in [05-data-model.md](05-data-model.md#voice) | yes | |
| Speech-verb list for the queue's "said X" rule | no | that rule is skipped |
| Dictionary for Respelling candidates | no | only Character names are offered as candidates |
| Listener-facing export lines (the AI-voice line, the AO3 commercial-use line) | no | the English lines are used |
| Chapter-heading patterns for TXT and PDF import: heading words and numbering styles ("Chapter 12", "CHAPTER XII", "Part One") | no | a TXT file is one chapter; a PDF uses only its bookmarks and font sizes |

- Line splitting is rule-based, with the rules from the pack. It is not done by the analysis model.
- Analysis prompts are always in English, for every Work; only the passage is in the Work's language. Emotion names are internal English ids, translated only in the interface. Packs carry no prompts.
- Auto-casting only draws from the built-in Voices of the Work's language.

## Interface language

- Every interface string goes through a message catalogue from milestone 1, including Emotion names, Voice labels and timbre words, warnings and job messages.
- English only until milestone 5, when Polish is filled in and a test starts failing whenever a string exists in one language and not the other.
- The interface follows the browser's language on first use; a remembered setting overrides it; any other language falls back to English.
- Text meant for listeners (export lines, the cover's title text) follows the Work's language. The upload checklist, which only the user reads, follows the interface language.
