# Chorus test samples

Test set for the listening test, the Speaker attribution prototype and the importers. Every story text is from Project Gutenberg and is public domain in the USA; the Project Gutenberg License applies to their editions. Check your local copyright law before publishing outside the USA.

## Passages (`passages/`): listening and Speaker attribution

Plain UTF-8 text, paragraphs separated by blank lines, `_underscores_` mark Gutenberg italics. Each file starts with a `#` header giving its source, word count and what it stresses.

| File | Work (Gutenberg #) | Words | What it stresses |
| --- | --- | --- | --- |
| `01-pride-and-prejudice-ch1-2.txt` | Pride and Prejudice, Austen (1342) | 1646 | Long untagged back-and-forth between two Characters, then several sisters join |
| `02-alice-mad-tea-party.txt` | Alice's Adventures in Wonderland, Carroll (11) | 1817 | Four Characters in one Scene, rapid untagged exchanges, sung verse |
| `03-holmes-scandal-in-bohemia.txt` | The Adventures of Sherlock Holmes, Doyle (1661) | 1622 | First-person narrator who is also a Character; a letter read aloud |
| `04-jane-eyre-ch1.txt` | Jane Eyre, Brontë (1260) | 1927 | First-person child narrator; calm to fear and fury; several adults at the end |
| `05-metamorphosis-opening.txt` | Metamorphosis, Kafka, tr. Wyllie (5200) | 1617 | Inner thoughts in quotation marks; voices through a closed door |
| `06-crime-and-punishment-opening.txt` | Crime and Punishment, Dostoevsky, tr. Garnett (2554) | 1679 | Quoted inner monologue that looks like dialogue; anxious Mood |

## Import files (`import/`): one per importer

| File | Format | Why it's here |
| --- | --- | --- |
| `pride-and-prejudice-gutenberg.epub` | EPUB 3 (Gutenberg, no images) | Baseline clean EPUB: a full novel with Gutenberg front and back matter to strip |
| `ao3-style-with-notes.epub` | EPUB, AO3 layout | **Synthetic.** Preface with work metadata, summary, beginning notes, per-chapter notes, end notes, italic thoughts. Story text is Metamorphosis; the AO3 metadata, author name and notes are invented. It mimics AO3's download layout but is not a real AO3 file. |
| `hard-two-column.pdf` | Text-layer PDF | **Synthetic.** Two columns, alternating running headers, page-number footers, 60 words hyphenated across line breaks, chapter heading mid-column. Text: Jane Eyre ch. I and the Holmes passage. Standard fonts, no layout tags. |
| `alice-gutenberg.azw3` | AZW3 (KF8) | Gutenberg's Kindle file (no DRM) |
| `alice-gutenberg.mobi` | MOBI (v6) | Gutenberg's older Kindle file (no DRM) |

Not included: a real AO3 download, because there's no public-domain one to redistribute and AO3's robots.txt disallows automated `/downloads/`. When needed, the user can download one of their own and test the upload path.

## Other folders

- `raw/`: the complete Gutenberg plain-text books the passages come from (`pg<id>.txt`), for whole-book runs.
- `build/`: the scripts that produced `passages/` and the two synthetic files (Python 3 standard library only). Run them from anywhere; their paths are absolute.
