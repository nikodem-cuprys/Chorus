# Chorus M1: the automatic path

The spec is [`docs/spec/`](../../docs/spec/README.md); this milestone is M1 in [`docs/spec/07-milestones.md`](../../docs/spec/07-milestones.md). Terms are those of [`CONTEXT.md`](../../CONTEXT.md).

**Shown when done:** import a file in any format except AO3, get a multi-voice Audio drama with no review, play it in the browser and export it as MP3 and M4B with chapters.

Build tickets are in `issues/`, one per file, each with a `Status:` triage label and a `Blocked by:` line. A ticket is unblocked when every ticket it lists is `resolved`.

| # | Ticket | Blocked by |
|---|---|---|
| 01 | Project skeleton: web, worker, queues, database, catalogue | none |
| 02 | The Chorus image on the frozen GPU stack | 01 |
| 03 | Character list on a whole novel | none |
| 04 | The English Language pack | 01 |
| 05 | EPUB import into a Work, end to end | 01, 04 |
| 06 | TXT import | 05 |
| 07 | PDF import | 05 |
| 08 | MOBI, AZW3 and other formats through Calibre | 02, 05 |
| 09 | The Script: kinds of text and line splitting | 04, 05 |
| 10 | First-run model download | 01, 02 |
| 11 | Analysis stage | 02, 03, 09, 10 |
| 12 | Auto-casting | 04, 11 |
| 13 | Voicing stage | 10, 12 |
| 14 | Chapter assembly and plain playback | 13 |
| 15 | Job control and progress | 11, 13 |
| 16 | MP3 and M4B export | 14 |
| 17 | README: host setup, responsible use, credits | 02 |
| 18 | M1 acceptance: listening and memory checks | 14, 15, 16 |

Frontier at the start: 01 and 03.
