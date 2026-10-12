# Chorus

Chorus turns a written work into a multi-voice audio drama with emotional delivery, keeps it in a personal library, and publishes it to external platforms.

## Language

### Input

**Source**:
The file or link a work is imported from: an ebook, document or plain-text file (EPUB, MOBI, PDF with a text layer, TXT, and other formats Calibre can convert), or an AO3 work.
_Avoid_: Input, upload, document

**Work**:
The text of a book or story after import, split into chapters, independent of the format it came from.
_Avoid_: Book, text, story

**Section break**:
A break inside a chapter, marked in the Source or set by the user, heard as a long pause. It is the only structure below a chapter.
_Avoid_: Scene, scene break

**Language pack**:
Everything Chorus needs to handle Works in one language: quotation rules, a voice model and built-in Voices, plus optional word lists and export lines. A Work's language picks its pack.
_Avoid_: Locale, translation (the interface's own language is separate)

### Analysis

**Speaker**:
Whoever voices a given line: the Narrator or a Character.
_Avoid_: Voice (a Voice is what a Speaker sounds like)

**Narrator**:
The Speaker for all voiced text that is not a Character's speech, thought or letter.

**Character**:
A person in the Work who speaks at least one line of dialogue.
_Avoid_: Role, persona

**Narrating Character**:
The Character who tells a chapter in the first person. The Narrator shares that Character's Voice for the chapter. A chapter told in the third person has none.
_Avoid_: First-person narrator, POV character

**Line**:
The smallest unit of a Script: one quotation, or one stretch of narration between quotations within a paragraph. Each line has one Speaker and is voiced as one piece of audio.
_Avoid_: Utterance, segment, sentence

**Speaker attribution**:
Deciding which Speaker says each line.
_Avoid_: Speaker detection, diarization

**Emotion**:
How a Character feels while saying one line. It sets how that line is delivered. The Narrator's lines have no Emotion and are always delivered neutrally.
_Avoid_: Sentiment, feeling, Mood

**Script**:
The analysed Work: every line with its Speaker and Emotion. It can be corrected before or after audio is generated.
_Avoid_: Screenplay, transcript

### Output

**Voice**:
A synthetic voice assigned to a Speaker.
_Avoid_: Speaker, model

**Respelling**:
A replacement spelling for one word of a Work, written as one ordinary-looking word, that the voice model reads instead of the original so the word is said correctly. It never changes the Script's text.
_Avoid_: Phonetic spelling, phonemes, alias

**Audio drama**:
The generated audio of a Work: a neutral Narrator and distinct Character Voices speaking with Emotion. It has no sound effects.
_Avoid_: Audiobook, podcast, rendering

**Library**:
The user's collection of Works and their Audio dramas.

**Publishing**:
Uploading an Audio drama from the app to an external platform.
_Avoid_: Export (Export means saving files locally)

**YouTube export**:
An Export of an Audio drama as one video per chapter, ready for the user to upload to YouTube by hand. It is not Publishing.
_Avoid_: YouTube upload, publish to YouTube
