# How special kinds of text are voiced

Type: grilling
Status: resolved
Blocked by: none

## Question

How does Chorus treat text that is neither plain narration nor dialogue: AO3 author notes and summaries, italic inner thoughts (the Script already marks speech or thought), letters, notes and text messages inside the story, footnotes, epigraphs, chapter titles and section breaks? For each: voiced or skipped by default, by whom (Narrator or a Character), in what delivery, and whether the user can switch it per Work. See the Work structure from ticket 03 and the samples in `../samples/`.

## Answer

Decided by the user on 2026-10-03 in a grilling session.

| Kind of text | Default | Who and how | Per-Work switch |
| --- | --- | --- | --- |
| AO3 summary and author notes (Work and chapter) | Skipped | Narrator, neutral, read where they stand | On |
| Tags, dedications, copyright pages, Gutenberg boilerplate | Skipped | Never voiced | None |
| Work title and author | Voiced | Narrator, once before chapter one, then a long pause | Off |
| Chapter title | Voiced | Narrator reads it as written, then a long pause; a chapter with no title gets nothing | Off |
| Epigraph (Work or chapter) | Voiced | Narrator, after the chapter title, then its source line, then a long pause | Off |
| Section break | Longest pause of the fixed set (ticket 17) | Nothing is said; a strong hint for a Scene start | None |
| Inner thought | Voiced | The thinking Character's Voice with the line's Emotion, never at strong intensity; no echo or filter | To the Narrator |
| Letter, note, text message set as its own block | Voiced | Its writer's Voice if the writer is a known Character, else the Narrator; neutral unless the user sets an Emotion; signature and date lines in the same Voice | None |
| Footnotes and endnotes | Skipped, marker dropped | Narrator, at the end of the paragraph, introduced by "Footnote" | On |
| Verse and songs | Voiced | Spoken, never sung, by whoever says it, with a short pause at each line end | None |
| Images, captions, tables of contents, page furniture | Skipped | Never voiced | None |
| Lists and tables inside the story | Voiced | Narrator, as plain text | None |

- **Emphasis:** italics or capitals used for stress, and italic titles of books or ships, change nothing in the delivery. Only italic passages judged to be thoughts are treated specially.
- **Thoughts, edge cases:** a thought whose thinker is unclear is read by the Narrator. In a first-person chapter a thought of the Narrating Character is voiced like any other thought: the same Voice as the narration, but with Emotion.
- **A letter read aloud in quotation marks** is ordinary dialogue, not a letter block.
- **Switches:** each Work has its own, on a settings panel; a global settings page holds the defaults a newly imported Work starts with. Changing a switch on a Work that already has audio puts the affected lines on the waiting list (ticket 20).
- **Per passage:** in the reading view any line or selection can be marked not voiced or voiced again, and its kind changed (narration, letter, verse, epigraph, footnote, note). These changes are pinned like other corrections.
- **Text that is not voiced** stays in the Script and the reading view, greyed out, and is not analysed for Speaker or Emotion.

This overrides the import research's first assumption that epigraphs are not narrated by default. CONTEXT.md: the Narrator's definition now covers letters and thoughts given to a Character.
