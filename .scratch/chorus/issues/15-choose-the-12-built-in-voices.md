# Choose the 12 built-in Voices by listening

Type: prototype
Status: resolved
Blocked by: 13

## Question

Which 12 of Kokoro's English voices become the built-in Voice library, and which one is the default Narrator? Render a neutral reference clip with each English Kokoro voice (about 28), clone each through Chatterbox 500M on the same short passage, and shortlist 12 for contrast: 6 women and 6 men, American and British accents, `bf_isabella` included (the best Voice in [ticket 07](07-voice-listening-test.md)). Build a listening page with the shortlist and the rejected voices; the user approves or swaps by ear and picks the default Narrator from the Voices flagged as suitable. Propose labels for each chosen Voice (gender, age band, accent, timbre words from a fixed list, Narrator flag) and the fixed timbre word list itself. Rules for the library are in [ticket 13](13-built-in-voice-library.md). Resolves with the 12 Voices, their labels, the default Narrator, and the reference clips saved for bundling.

## Answer

The 12 built-in Voices, chosen by the user by ear on 2026-10-01 from all 28 English Kokoro voices cloned through Chatterbox 500M (torch 2.14.0+cu126). Default Narrator: `af_bella`.

| Voice (Kokoro id) | Gender | Accent | Age | Timbre | Suits the Narrator |
|---|---|---|---|---|---|
| `af_alloy` | female | American | adult | low, dark, measured | no |
| `af_aoede` | female | American | adult | dark | yes |
| `af_bella` | female | American | adult | high, measured | yes (default) |
| `af_heart` | female | American | adult | high | no |
| `af_kore` | female | American | adult | low, dark, measured | no |
| `bf_emma` | female | British | adult | bright | yes |
| `am_eric` | male | American | adult | high, dark, measured | no |
| `am_fenrir` | male | American | young adult | high | yes |
| `am_michael` | male | American | adult | bright, measured | yes |
| `bm_daniel` | male | British | adult | bright, brisk | no |
| `bm_fable` | male | British | adult | low, dark, brisk | no |
| `bm_lewis` | male | British | adult | low | no |

- **Changes from the shortlist:** the user swapped `af_river` and `bf_isabella` out for `af_heart` and `af_kore`; the six men were kept as shortlisted. `bf_isabella`, the best Voice in ticket 07, is not in the library.
- **Accent spread:** 5 American and 1 British among the women; 3 and 3 among the men.
- **Fixed timbre word list:** low, high, bright, dark, brisk, measured, warm, soft, gruff, crisp. The first six were pre-ticked from measurements (pitch, brightness, pace, in thirds within each gender) and left as measured. No Voice was given warm, soft, gruff or crisp.
- **Narrator:** five Voices are flagged as suitable (`af_aoede`, `af_bella`, `bf_emma`, `am_fenrir`, `am_michael`).
- **Shortlist method:** the six women and six men furthest apart by the speaker embedding Chatterbox derives from each reference clip, with a small bonus for Kokoro's quality grade. It measures difference, not quality; the user overrode it for two voices.
- **Pasted choices:** the paste was cut in the middle of the `af_kore` entry. Its timbre was read as low, dark, measured, which matches both the pasted text on either side of the cut and the pre-ticked values.

Saved for bundling: `../prototypes/voice-library/library/` (12 reference clips of about 11 s at 24 kHz, and `voices.json` with labels, language, default Narrator, the timbre word list and a `clips` map that can hold more clips per Voice later). Listening page and all 28 clones: `../prototypes/voice-library/listen.html`, `out/`.
