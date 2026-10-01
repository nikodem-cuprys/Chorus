# How you review and correct the Script

Type: prototype
Status: resolved
Blocked by: none

## Question

What should correcting a Script look like? Review is optional and happens after automatic generation. Decide what the user can change (the Speaker of a line, its Emotion, splitting and merging text, merging Characters that are aliases, the Voice per Character); how corrections are applied (to one line, to all lines of a Character, or to the rest of the Work); and what gets regenerated afterwards. Research found that the Character list and its aliases are the hardest part of Speaker attribution, so that list belongs in the Script and user fixes to it must survive regeneration (see `../research/analysis-models-in-4gb.md`). Resolve with a rough clickable UI mock-up for the user to react to.

## Comments

- 2026-10-01, prototype built, waiting for the user's verdict. `../prototypes/script-review/review.html` (double-click; `data.js` is built by `build.py` from the approach B Scripts of ticket 08). Three variants on the six sample passages, switched with the bar at the bottom, the arrow keys or `?variant=A|B|C`. Nothing is saved; corrections live in memory and survive a variant switch.
  - A, Reading view: the Work as prose with each line tinted by Speaker. Click a line to change Speaker, Emotion, intensity, speech/thought, split it or join it with the next; choose whether the change applies to this line, the selected lines, the Speaker's lines from here on, or all of the Speaker's lines. Shift-click selects a run; "swap the two Speakers" fixes lost turn-taking. Cast on the right: rename, Voice with a sample, merge into another Character, remove, drop an alias. Scenes show as dividers with a Mood picker and "merge with the Scene above".
  - B, Cast board: one column per Speaker plus Unknown and quoted lines given to the Narrator. Drag a line (or several ticked lines) to another column; drag a column header onto another to merge two Characters. No Scene or text editing.
  - C, Question queue: only the lines Chorus is unsure about, one at a time with context; number keys pick a Speaker, Enter keeps the guess, S skips. It also asks about Characters with a single line and Scenes that repeat the previous setting.
  - Shared by all three: the top bar counts lines to re-voice with a rough time, Regenerate, Undo, and a Changes panel listing corrections and the lines waiting for audio. Corrected lines and Characters carry a pin meaning "kept if the Script is analysed again".
  - The queue's questions come from four rules (no Speaker, thought or quoted line given to the Narrator, the line names its own Speaker, deep in an untagged exchange), because the model gives no confidence score. Over the six passages they raise 70 questions and cover 14 of the 21 lines approach B got wrong against the ticket 08 reference: all 7 in Metamorphosis and 5 of 6 in Pride and Prejudice, none of the 5 in Holmes, Jane Eyre and Crime and Punishment.
  - Checked: a scripted run of every correction, undo and the queue on all six passages, and a screenshot of each variant. Not clicked through by hand in a browser: the line editor pop-up in A and drag-and-drop in B are untested.
  - Assumed, for the user to confirm: only lines whose Speaker's Voice, Emotion, intensity or text changed are re-voiced, then the chapter is re-assembled; a Voice change re-voices all of that Character's lines; in a first-person Work the Narrator uses the narrating Character's Voice.

## Answer

Decided by the user on 2026-10-01 after seeing the three variants: the Reading view (A) is the main Script review screen, and the Question queue (C) is the way in. The Cast board (B) is dropped.

- **Entry:** review opens on the queue of lines Chorus is unsure about, one at a time with context; the user picks a Speaker, keeps the guess or skips. It also asks about Characters with a single line and Scenes that repeat the previous setting. The queue is optional, like review itself.
- **Main screen:** the Work as prose with each line tinted by its Speaker, and the cast beside it. Every line can be corrected here, whether or not the queue asked about it.
- **What the user can change:** a line's Speaker, Emotion, intensity and speech/thought; split a line or join it with the next; add, rename, merge and remove Characters and drop an alias; the Voice per Character and for the Narrator; a Scene's Mood, and merge a Scene into the one before.
- **How a correction is applied:** to this line, to the selected lines, to that Speaker's lines from here on, or to all of that Speaker's lines. Merging Characters and changing a Voice apply to the whole Work.
- **What survives:** corrected lines and Characters are pinned, and a new analysis of the Work must keep them. The Character list with its aliases is part of the Script.

Not confirmed by the user, carried as assumptions from the prototype: only lines whose Voice, Emotion, intensity or text changed are re-voiced, then the chapter is re-assembled; a Voice change re-voices all of that Character's lines; in a first-person Work the Narrator uses the narrating Character's Voice.

Known gap: the queue's four rules cover 14 of the 21 lines approach B got wrong on the sample passages (70 questions), so the main screen must stay the place where the remaining errors are found. The prototype was not clicked through by hand before the verdict.

Prototype kept in `../prototypes/script-review/` (`review.html`, `data.js`, `build.py`).
