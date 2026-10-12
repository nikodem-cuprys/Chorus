# Scope

## What Chorus does

1. **Imports a Source** into a Work. Sources are ebooks, documents and plain-text files (EPUB, MOBI, AZW3, PDF with a text layer, TXT, and any other format Calibre can convert, such as DOCX, FB2, RTF, HTML and ODT) and AO3 works, either by URL or as an uploaded AO3 download.
2. **Analyses the Work into a Script:** splits it into lines, finds the Characters and their aliases, decides the Speaker of every line (Speaker attribution), the Narrating Character of each chapter, and the Emotion and intensity of every Character line.
3. **Casts Voices** automatically from 12 built-in Voices. The user can swap any Voice and clone new ones from their own clips.
4. **Voices the Script** into an Audio drama: a neutral Narrator and distinct Character Voices with Emotion. No sound effects, no music.
5. **Lets the user review and correct** the Script afterwards, if they want. Review is optional: the default path is fully automatic. A correction re-voices only what changed.
6. **Keeps everything in the Library,** where the reading view also works as the player.
7. **Exports** MP3 and M4B with chapters, and YouTube exports (one video per chapter, uploaded by hand).
8. **Publishes** to YouTube directly with one click, as the final milestone, and shows the channel's statistics for the uploaded videos.

## Standing constraints

- **Self-hosted, single user,** used through a browser. Shipped as Docker with NVIDIA GPU support, on Windows (WSL2) and Linux.
- **Local-first:** the whole default pipeline runs offline on free models. Network access is used only for downloading models on first run, AO3 import by URL, and YouTube.
- **Minimum hardware: a GTX 1050 Ti** (4 GB, Pascal, compute capability 6.1) for every stage, including analysis. Slowness is acceptable: a novel takes about a day to voice.
- **English first.** English is the only Language pack in the first build. Nothing in the design may block a second language (see [02-architecture.md](02-architecture.md#language-packs)).
- **Quality is judged by listening,** not by a formal benchmark.
- **Licences:** prefer models and libraries that allow commercial use, and flag any that do not. Every chosen model and library allows commercial use (see [04-models-and-libraries.md](04-models-and-libraries.md)). Chorus itself is MIT.
- **Inform, never block:** Chorus warns about authors' permissions and AI disclosure but never refuses an action on those grounds (see [03-pipeline.md](03-pipeline.md#permissions-and-disclosure)).

## Out of scope

- Sound effects, background music and ambience.
- Spotify and podcast publishing; only exported files.
- OCR for scanned, image-only PDFs. Such files are rejected with a clear message.
- DRM-protected files. They are rejected with a clear message, never decrypted.
- Multiple users and hosted SaaS.
- A formal accuracy benchmark.
- A change of storyteller inside one chapter.
- A language per chapter or per line: a Work has one language.
- Offline listening on a phone or an app; the user exports an M4B for that.
- Singing: verse and songs are spoken.
