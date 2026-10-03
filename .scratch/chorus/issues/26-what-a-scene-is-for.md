# What a Scene is for

Type: grilling
Status: resolved
Blocked by: none

## Question

With Mood dropped (ticket 17), a Scene is a stretch of a chapter with one setting, and nothing decided so far uses it in the audio. Ticket 09 lets the user merge Scenes and asks about Scenes that repeat the previous setting; ticket 21 makes a section break the longest pause and a hint for a Scene start. Decide whether the Script keeps Scenes at all. If it does: what they do (grouping in the reading view, a pause at a Scene change that has no section break, marks inside a long chapter, context for the analysis model), whether the review queue still asks about them, and what the user can do to them. If it does not: remove the term from `CONTEXT.md` and the Scene controls from the review screen.

## Answer

Decided by the user on 2026-10-03 in a grilling session: the Script does not keep Scenes.

- **Dropped:** the analysis no longer outputs Scenes or settings. It may still cut the text into chunks internally (ticket 08); the user never sees those.
- **Review:** the Scene dividers and the "merge with the Scene above" control leave the reading view, and the queue no longer asks about Scenes that repeat the previous setting. Its questions about lines and single-line Characters stay.
- **Section breaks:** the only structure below a chapter. A Section break comes from the Source and is heard as the longest pause (ticket 21). In the reading view it shows as a divider; the user can remove one or insert one between any two lines. That changes only the pause, so no line is re-voiced and the chapter is re-assembled. The change is pinned like other corrections.
- **Player:** jump points are chapters, lines and bookmarks only.
- **Amends:** ticket 09 (Scene controls and Scene questions) and ticket 21's remark that a section break is a hint for a Scene start.
- **Glossary:** `CONTEXT.md` loses Scene, gains Section break, and the Script becomes every line with its Speaker and Emotion.

Reasons: with Mood gone a Scene carried only a setting that nothing in the audio used, Scene detection was unreliable (ticket 08), and the Source's own breaks already give the pause.
