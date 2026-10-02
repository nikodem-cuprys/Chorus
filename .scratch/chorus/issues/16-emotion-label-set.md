# The Emotion list and how Chatterbox voices each Emotion

Type: prototype
Status: open
Blocked by: 07, 14

## Question

Which fixed list of Emotions does a Script use, and what Chatterbox 500M settings (`exaggeration`, `cfg_weight`, and whatever "intensity" scales) voice each one so it sounds right by ear? The listening test used one setting per Emotion for 7 Emotions without tuning (`../prototypes/voice-listening-test/`). Render a few lines per candidate Emotion and intensity with two or three built-in Voices, and check two things alongside: that a Voice stays recognisable at the strongest settings, and whether a fixed seed makes a regenerated line sound the same as before (Chatterbox samples at random). Resolves with the Emotion list, the settings for each Emotion and intensity, and whether lines are generated with a fixed seed.
