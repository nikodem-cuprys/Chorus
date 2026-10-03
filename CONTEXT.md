# Chorus

Chorus turns a written work into a multi-voice audio drama with emotional delivery, keeps it in a personal library, and publishes it to external platforms.

## Language

### Input

**Source**:
The file or link a work is imported from (PDF, EPUB, MOBI, or an AO3 work).
_Avoid_: Input, upload, document

**Work**:
The text of a book or story after import, split into chapters, independent of the format it came from.
_Avoid_: Book, text, story

### Analysis

**Speaker**:
Whoever voices a given line: the Narrator or a Character.
_Avoid_: Voice (a Voice is what a Speaker sounds like)

**Narrator**:
The Speaker for all text that is not a Character's direct speech.

**Character**:
A person in the Work who speaks at least one line of dialogue.
_Avoid_: Role, persona

**Speaker attribution**:
Deciding which Speaker says each line.
_Avoid_: Speaker detection, diarization

**Scene**:
A continuous stretch of a chapter with one setting.

**Emotion**:
How a Character feels while saying one line. It sets how that line is delivered. The Narrator's lines have no Emotion and are always delivered neutrally.
_Avoid_: Sentiment, feeling, Mood (a Scene has no emotional label)

**Script**:
The analysed Work: every line with its Speaker, Emotion and Scene. It can be corrected before or after audio is generated.
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
