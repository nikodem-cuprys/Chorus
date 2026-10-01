# Policy on permission to publish other authors' works and consent for cloned voices

Type: grilling
Status: resolved
Blocked by: none

## Question

What should Chorus do, if anything, about (a) publishing Audio dramas of works the user did not write (AO3 fanworks, where recording one as a "podfic" usually needs the author's permission, and copyrighted books) and (b) cloning a real person's voice? Options range from doing nothing, to a warning or confirmation checkbox, to recording permission per Work or per Voice, to blocking Publishing without permission. Note: AO3's Terms of Service ban commercial use of its content, which conflicts with possible future monetization of Published AO3-based Audio dramas (see `../research/source-import-libraries.md`). Also decide whether YouTube uploads should carry an AI-generated content disclosure by default (research recommends `containsSyntheticMedia` on by default and forced on for cloned Voices), and what to do about Chatterbox's built-in audio watermark if that model is chosen.

## Answer

Decided by the user on 2026-10-01 in a grilling session. Chorus informs and does not police: nothing is blocked, and almost nothing is recorded.

- **Works the user did not write:** one warning, shown once ever, the first time the user makes a YouTube export or Publishes. It says the author's permission is needed, including podfic permission for fanworks. Nothing is recorded per Work and nothing is blocked. Import, generation, listening in the Library and MP3/M4B export never ask.
- **Cloning a voice:** no question and no checkbox when a clip is added.
- **AO3 and commercial use:** Chorus remembers that the Source was AO3 and shows one line about the AO3 Terms of Service ban on commercial use in the YouTube export checklist and on the Publishing screen, every time. No blocking.
- **AI disclosure at Publishing:** `containsSyntheticMedia` is on by default and the user can turn it off per Work. The first time a cloned Voice is in a Work being Published, Chorus asks "is this your own voice?" and stores the answer on the Voice. If the voice is not the user's own, the flag is forced on.
- **YouTube export:** unchanged from ticket 12 (general reminder in the checklist to tick YouTube's box, AI-voices line in the description). It does not use the own-voice answer.
- **Chatterbox watermark:** kept by default. One global switch in Settings turns it off for audio generated afterwards; existing audio keeps what it was made with. Claude recommended keeping it always, with no switch; the switch is the user's decision.
- **Written note:** a few lines in the README on the author's permission, the speaker's consent and the AO3 commercial-use point. Nothing extra in the app.

Options the user turned down: a recorded rights statement per Work, a required "my own voice / with consent" choice when cloning, and reusing the own-voice answer in the YouTube export checklist.
