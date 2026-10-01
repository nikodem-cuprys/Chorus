# Where the built-in Voice library comes from

Type: grilling
Status: resolved
Blocked by: 07

## Question

Zero-shot voice models have no fixed voice set; built-in Voices for auto-casting will be a bundled library of reference clips (see `../research/tts-models-for-1050ti.md`). Where should those clips come from: generated with a voice-design model (e.g. Qwen3-TTS 1.7B VoiceDesign run on CPU), curated from openly licensed speech corpora (e.g. VCTK, LibriTTS), or both? Decide the size of the library, which traits each Voice is tagged with for auto-casting (gender, age, accent, timbre), and the license requirements given possible future monetization.

## Answer

The built-in Voice library is 12 English Voices, each one neutral reference clip rendered with Kokoro, made once during development and bundled as audio files. Decided by grilling on 2026-10-01.

Library:
- **Source:** generated clips only, all from Kokoro's English voices (Apache-2.0). No real recordings, no Qwen VoiceDesign.
- **License rule:** a source must allow commercial use; a required credit is acceptable. Chorus ships a credits list naming Kokoro.
- **Size:** 12 Voices: 6 women and 6 men, American and British accents, all adults.
- **Labels:** gender (female, male, neutral), age band (child, young adult, adult, elderly), accent (American, British), two or three timbre words from a fixed list, and a "suits the Narrator" flag.
- **Clips per Voice:** one neutral clip now. The library format must allow extra emotional clips per Voice later.
- **Shipping:** prebuilt and bundled. Kokoro is not a runtime dependency.
- **Languages:** English only for now. Each Voice records its language so other sets can be added without changing the format or the casting rules.

Casting:
- **Narrator:** one fixed default Narrator Voice for every Work; the user can swap it. It is never given to a Character, which leaves 11 Voices for Characters.
- **Large casts:** Characters with the most lines get unique Voices. The rest share the closest match by labels, avoiding two Characters with the same Voice in one Scene where possible.
- **Cloned Voices:** stored in the same library with the same labels, filled in by the user. Used only when the user assigns them; auto-casting uses built-in Voices only.

Consequences:
- Child and elderly Characters get the closest adult Voice by gender; Kokoro has no child or elderly voices.
- The "child", "elderly" and "neutral" labels exist but no built-in Voice carries them; they only matter for cloned Voices.
- Which 12 voices, their labels, and the default Narrator are chosen by listening in [ticket 15](15-choose-the-12-built-in-voices.md).

## Comments

- 2026-10-01, from the listening test ([ticket 07](07-voice-listening-test.md)): the best Voice was young Jane, whose reference clip was generated with Kokoro `bf_isabella`; the worst was the Narrator, cloned from a real LibriVox recording (Annie Coleman). So a generated reference clip can work well, and a real recording is not automatically better (one clip of each kind was singled out, so this is a hint, not a finding). The default model is Chatterbox 500M, so library clips must clone well with it.
