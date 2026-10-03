# The Emotion list and how Chatterbox voices each Emotion

Type: prototype
Status: resolved
Blocked by: 07, 14

## Question

Which fixed list of Emotions does a Script use, and what Chatterbox 500M settings (`exaggeration`, `cfg_weight`, and whatever "intensity" scales) voice each one so it sounds right by ear? The listening test used one setting per Emotion for 7 Emotions without tuning (`../prototypes/voice-listening-test/`). Render a few lines per candidate Emotion and intensity with two or three built-in Voices, and check two things alongside: that a Voice stays recognisable at the strongest settings, and whether a fixed seed makes a regenerated line sound the same as before (Chatterbox samples at random). Resolves with the Emotion list, the settings for each Emotion and intensity, and whether lines are generated with a fixed seed.

## Answer

Nine Emotions, each with two intensities (normal and strong), chosen by the user by ear on 2026-10-02 and 2026-10-03 with Chatterbox 500M (torch 2.14.0+cu126) on the Voices `af_bella` and `bm_lewis`. Lines are generated with a fixed seed.

| Emotion | Normal (`exaggeration` / `cfg_weight`) | Strong | From the listening |
|---|---|---|---|
| neutral | 0.5 / 0.5 | same | no intensity |
| happy | 0.6 / 0.5 | 0.75 / 0.45 | above 0.8 is "extreme agitation" |
| excited | 0.7 / 0.4 | 0.9 / 0.35 | at 1.2 the Voice is barely recognisable |
| amused | 0.55 / 0.5 | 0.7 / 0.45 | at 0.85 the voice breaks; 0.7 and 0.85 sound alike |
| angry | 0.7 / 0.4 | 0.9 / 0.3 | 0.7 is "irritated"; 0.8 and 0.9 are "natural angry"; 1.0, 1.2 and 1.4 are too aggressive and the voice breaks at 1.4 |
| sad | 0.4 / 0.4 | 0.25 / 0.2 | picked over 0.3 / 0.3 and over more expressive tries (0.6, 0.8) |
| afraid | 0.7 / 0.4 | 0.9 / 0.35 | at 1.2 it sounds excited, not afraid |
| anxious | 0.4 / 0.4 | 0.6 / 0.45 | "lower the better"; 0.4 picked as the best |
| surprised | 0.7 / 0.45 | same | above 0.7 it sounds angry |

- **Emotion list:** neutral, happy, excited, amused, angry, sad, afraid, anxious, surprised. Disgusted is removed: it had no audible intensity steps, the Voice was not recognisable, and the user found it indistinct from anxious. The analysis prompt from ticket 08 uses 10 Emotions and must drop it.
- **Intensity:** two levels. The user heard only two distinct steps for every Emotion except angry, and angry's third step was too aggressive. Neutral and surprised use one setting for both levels.
- **Ceiling:** no Emotion goes above `exaggeration` 0.9. The user named 0.8 as standard expression and 1.2 as the most agitated acceptable on a plain line, but rejected every Emotion line rendered at 1.0 or more.
- **What the dials carry:** at the strongest settings a plain line sounded like the Emotion for happy, amused, angry and sad, and only livelier for excited, afraid, anxious and surprised. For those four the words do most of the work.
- **Voice recognisability:** similarity to the Voice's reference clip (Chatterbox's own voice encoder) is 0.91 or more on both Voices for most chosen settings and about 0.89 at the lowest (excited strong on `bm_lewis`). At 1.2 and above it mostly fell to between 0.81 and 0.88. `bm_lewis` drifts more than `af_bella`.
- **Seed:** two renders of a line with `torch.manual_seed(0)` came out the same take on both Voices (same length, differing by at most one 16-bit step); seed 1 gave a different take. So each line stores its seed, a regenerated line reuses it, and a new take changes it. The user did not rate how different the seed-1 takes sound.
- **Not settled by ear:** strong angry is 0.9 because the user heard little difference between 0.8 and 0.9. The user also noted that `cfg_weight` 0.3 "gives a better impression" on the dials grid; the per-Emotion `cfg_weight` values were not re-tuned for that. Only two of the 12 Voices were tested.
- **Machine note:** Norton's HTTPS scanning made the Hugging Face check fail from Python on 2026-10-03; the clips were rendered offline (`HF_HOME` set to `../prototypes/voice-listening-test/hf-cache`, `HF_HUB_OFFLINE=1`).

Settings saved in `../prototypes/emotion-settings/emotions.json`. Listening page, scripts and all 132 clips: `../prototypes/emotion-settings/` (`listen.html`, `gen.py`, `out/`).
