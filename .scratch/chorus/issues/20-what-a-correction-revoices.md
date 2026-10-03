# What a correction re-voices, and who narrates a first-person Work

Type: grilling
Status: resolved
Blocked by: none

## Question

Ticket 09 carried three assumptions the user never confirmed: only lines whose Voice, Emotion, intensity or text changed are re-voiced, then the chapter is re-assembled; a Voice change re-voices all of that Character's lines; in a first-person Work the Narrator uses the narrating Character's Voice. Confirm or change them. Also decide what happens when the user corrects lines while the Work is still being voiced or exported, and how a long job reports progress and is paused, cancelled or resumed after a crash (ticket 11 saves every finished chunk and line).

## Answer

Decided by the user on 2026-10-03 in a grilling session. The three assumptions from ticket 09 are confirmed, the third in a sharper form.

- **What is re-voiced:** only lines whose Voice, Emotion, intensity or text changed; the chapter is then re-assembled. Neighbouring lines are untouched. A changed Speaker counts as a changed Voice. A Voice change re-voices all of that Character's lines, and a Narrator Voice change re-voices all narration. Splitting or joining lines re-voices the resulting lines. A new Respelling re-voices every line containing the word (ticket 19).
- **When:** on Regenerate. Corrections collect as lines waiting for audio, with a count and a rough time; nothing is voiced until the user presses Regenerate.
- **Meanwhile:** the old audio keeps playing so the chapter stays whole, and waiting lines carry a visible mark in the reading view. Lines never voiced (for example just split) are skipped by the player.
- **New take:** a re-voiced line keeps its stored seed (ticket 16), so only what the user changed changes. A "New take" button on a line picks a new seed and puts the line on the waiting list.
- **After a new analysis:** a line keeps its audio if its Speaker, Emotion, intensity and text came out the same.
- **First-person Works:** each chapter records its narrating Character (or none, for third person), detected automatically and correctable. The Narrator and the narrating Character share one Voice, auto-cast by that Character's traits; the user can separate them in the cast. Narration stays neutral (ticket 17); the Character's spoken lines carry Emotion. Changing a chapter's narrating Character re-voices that chapter's narration. A change of storyteller inside one chapter is not handled. This is the one exception to ticket 13's rule that the Narrator's Voice is never given to a Character.
- **Correcting while the Work is being voiced:** allowed, and the running job is never restarted. Lines not voiced yet use the corrected values when their turn comes; lines already voiced join the waiting list. Pressing Regenerate during the job queues the waiting lines after it.
- **Correcting during or after an Export or YouTube export:** the export uses the audio as it was when it started and always finishes; once lines are re-voiced it, and each affected chapter video, is flagged outdated (as in ticket 12).
- **Exporting with lines waiting:** Chorus says how many lines are waiting and offers "Regenerate, then export" or "Export anyway" (old audio, flagged outdated straight away). It does not block.
- **Job controls:** pause, resume and cancel for analysis, voicing and export. Pause stops after the current line or chunk and frees the GPU. Cancel keeps every finished line, so starting again does only what is missing; throwing audio away is a separate, explicit action.
- **After a crash or reboot:** a running job resumes by itself when Chorus is back up; a paused job stays paused.
- **Progress:** the stage, chapter x of y, lines done of total, a percentage and a time-left estimate from the measured speed, on the Work's page and in the Library.

CONTEXT.md gains the term Narrating Character.
