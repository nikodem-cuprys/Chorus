# Collect a sample set of test passages from different kinds of books

Type: task (AFK)
Status: resolved
Blocked by: none

## Question

Assemble a small test set for listening and Speaker attribution in `.scratch/chorus/samples/`: 4-6 passages of about 1-2k words each, from public-domain or freely licensed works (e.g. Project Gutenberg). Choose them to stress Speaker attribution and Emotion: heavy back-and-forth dialogue without speaker tags, many Characters in one Scene, a first-person narrator, strong emotional shifts, and inner thoughts. Also include import test files: at least one hard PDF (running headers, hyphenation, two columns), one AO3-style EPUB with author notes, and one AZW3/MOBI. Record the source and license of each. Done when the files exist and are listed in the resolution.

## Answer

Done. The test set is in `.scratch/chorus/samples/`, indexed in [samples/README.md](../samples/README.md) with source, license and what each file stresses.
- **Passages (6, 1.6-1.9k words each, all Project Gutenberg, US public domain):** Pride and Prejudice ch. 1-2 (untagged back-and-forth), Alice's "A Mad Tea-Party" (four Characters in one Scene), "A Scandal in Bohemia" opening (first-person narrator who is also a Character), Jane Eyre ch. I (emotional escalation), Metamorphosis opening (quoted inner thoughts, voices through a door), Crime and Punishment opening (inner monologue that looks like dialogue).
- **Import files:** a clean Gutenberg EPUB 3 (Pride and Prejudice); a synthetic AO3-layout EPUB with preface metadata, summary, beginning, chapter and end notes; a synthetic hard PDF (two columns, running headers, page-number footers, 60 words hyphenated across line breaks); Gutenberg AZW3 and MOBI of Alice.
- **Facts for later tickets:** there's no real AO3 download in the set, because none is redistributable and robots.txt disallows `/downloads/`; the AO3 EPUB is modelled on AO3's layout, not copied. The PDF is untested by a PDF reader or renderer; only its structure was checked. Build scripts are in `samples/build/`, and the complete source books are in `samples/raw/`.
