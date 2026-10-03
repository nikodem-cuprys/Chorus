"""PROTOTYPE, throwaway (ticket 16). Build listen.html from the clips gen.py rendered.
Run with any Python that has numpy + soundfile (e.g. the frozen-stack env): python build_page.py"""
import html, json, pathlib
import numpy as np, soundfile as sf
from gen import EMOTIONS, INTENSITIES, DIAL_EX, DIAL_CFG, SEED_LINES, VOICES, NEUTRAL_TEXT, ROUND2

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"


def info(part, voice, key):
    f = OUT / part / voice / f"{key}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def clip(part, voice, key, label=""):
    i = info(part, voice, key)
    if not i:
        return f'<div class="clip missing">{html.escape(label)} not rendered yet</div>'
    sim_cls = " bad" if i["speaker_sim"] < 0.9 else ""
    return (f'<div class="clip"><div class="lab">{html.escape(label)} <span class="meta">ex {i["ex"]} · cfg {i["cfg"]}'
            f' · <span class="{sim_cls}">sim {i["speaker_sim"]:.2f}</span> · {i["words_per_s"]} w/s</span></div>'
            f'<audio controls preload="none" src="out/{part}/{voice}/{key}.wav"></audio></div>')


def same_audio(voice, a, b):
    fa, fb = (OUT / "seed" / voice / f"{k}.wav" for k in (a, b))
    if not (fa.exists() and fb.exists()):
        return "not rendered yet"
    x, _ = sf.read(fa)
    y, _ = sf.read(fb)
    if x.shape == y.shape and np.array_equal(x, y):
        return "identical, sample for sample"
    if x.shape == y.shape and np.abs(x - y).max() <= 2 / 32768:  # 16-bit rounding, inaudible
        return "the same take (same length; differs only by 16-bit rounding, inaudible)"
    n = min(len(x), len(y))
    return f"different (lengths {len(x)} vs {len(y)} samples; max difference {np.abs(x[:n] - y[:n]).max():.3f})"


sections = []

# Round 2: only what the first verdicts left unheard
r2 = []
R2_ASK = {"sad": "Which setting is the strong sad you wanted?",
          "anxious": "Which setting is the best anxious?",
          "angry": "Which setting is the best strong angry (1.0 and above were too aggressive)?"}
R2_REF = {"sad": [("emotions", "sad_low", "round 1 low"), ("emotions", "sad_high", "round 1 high")],
          "anxious": [("emotions", "anxious_low", "round 1 low")],
          "angry": [("emotions", "angry_low", "round 1 low"), ("emotions", "angry_medium", "round 1 medium")]}
for emo, settings in ROUND2.items():
    per_voice = []
    for v in VOICES:
        clips = "".join(clip(p, v, k, lab) for p, k, lab in R2_REF[emo])
        clips += "".join(clip("round2", v, f"{emo}_ex{ex}_cfg{cfg}", "new") for ex, cfg in settings)
        per_voice.append(f'<div class="voice"><h4>{v}</h4>{clips}</div>')
    opts = "".join(f"<option>ex {ex} · cfg {cfg}</option>" for ex, cfg in settings)
    opts += "".join(f"<option>{lab}</option>" for _, _, lab in R2_REF[emo]) + "<option>none of these</option>"
    r2.append(f'<div class="emo"><h3>{emo}</h3><p class="text">"{html.escape(EMOTIONS[emo]["text"])}"</p>'
              f'<div class="voices">{"".join(per_voice)}</div><div class="verdict">'
              f'<label>{R2_ASK[emo]} <select data-k="r2.{emo}.pick"><option value="">-</option>{opts}</select></label>'
              f'<label>Notes <input data-k="r2.{emo}.notes"></label></div></div>')
sections.append(f"""<section><h2>Round 2: the settings you have not heard yet</h2>
<p>Sad was "needs stronger" (tried in both directions), anxious was "lower the better", and angry is tried at 1.2,
the ceiling you named. Round 1 clips are repeated beside them for comparison.</p>{''.join(r2)}</section>""")

# Part 1: the dials
rows = []
for v in VOICES:
    cells = "".join(f'<tr><th>exaggeration {ex}</th>' +
                    "".join(f"<td>{clip('dials', v, f'ex{ex}_cfg{cfg}')}</td>" for cfg in DIAL_CFG) + "</tr>"
                    for ex in DIAL_EX)
    rows.append(f'<h3>{v}</h3><table><tr><th></th>' +
                "".join(f"<th>cfg_weight {c}</th>" for c in DIAL_CFG) + f"</tr>{cells}</table>")
sections.append(f"""<section><h2>1. What the two dials do</h2>
<p>One plain line, <span class="text">"{html.escape(NEUTRAL_TEXT)}"</span>, across exaggeration and cfg_weight.
Listen down a column (exaggeration) and across a row (cfg_weight). <b>sim</b> is how close the output is to the
Voice's reference clip by Chatterbox's own voice encoder (below 0.90 shown red); <b>w/s</b> is words per second.</p>
{''.join(rows)}
<label>How many clearly different deliveries do you hear, and where do the dials stop being useful?
<textarea data-k="dials"></textarea></label></section>""")

# Part 2: each Emotion
emo_rows = []
for emo, e in EMOTIONS.items():
    per_voice = []
    for v in VOICES:
        if emo == "neutral":
            clips = clip("emotions", v, "neutral_low", "neutral")
        else:
            clips = "".join(clip("emotions", v, f"{emo}_{i}", i) for i in INTENSITIES)
            clips += clip("emotions", v, f"{emo}_neutraltext", "high settings, plain line")
        per_voice.append(f'<div class="voice"><h4>{v}</h4>{clips}</div>')
    verdict = "" if emo == "neutral" else f"""
<div class="verdict">
<label>Emotion <select data-k="{emo}.verdict"><option value="">-</option><option>keep</option>
<option>keep, needs stronger settings</option><option>keep, needs weaker settings</option>
<option>merge into another Emotion</option><option>drop</option></select></label>
<label>Intensity steps <select data-k="{emo}.steps"><option value="">-</option><option>three distinct steps</option>
<option>only two distinct</option><option>no audible difference</option></select></label>
<label>Voice still recognisable at high <select data-k="{emo}.voice"><option value="">-</option><option>yes</option>
<option>barely</option><option>no</option></select></label>
<label>Plain line at high settings <select data-k="{emo}.plain"><option value="">-</option>
<option>sounds like this Emotion</option><option>sounds just livelier</option><option>no change</option></select></label>
<label>Notes <input data-k="{emo}.notes"></label></div>"""
    emo_rows.append(f'<div class="emo"><h3>{emo}</h3><p class="text">"{html.escape(e["text"])}"</p>'
                    f'<div class="voices">{"".join(per_voice)}</div>{verdict}</div>')
sections.append(f"""<section><h2>2. Each candidate Emotion at low, medium and high</h2>
<p>These are the 10 Emotions the analysis prompt already uses (ticket 08), with starting settings guessed from the
listening test. The fourth clip reads the plain line at the Emotion's high settings: if it sounds like the Emotion,
the settings carry it; if it only sounds livelier, the words do the work.</p>
{''.join(emo_rows)}
<label>Missing Emotions, or ones you would merge (e.g. afraid + anxious)? <textarea data-k="list"></textarea></label>
</section>""")

# Part 3: seed
seed_rows = []
for v in VOICES:
    for emo in SEED_LINES:
        a, b, c = f"{emo}_seed0a", f"{emo}_seed0b", f"{emo}_seed1c"
        seed_rows.append(f'<div class="emo"><h4>{v} · {emo}</h4><div class="voices">'
                         f'{clip("seed", v, a, "seed 0, run 1")}{clip("seed", v, b, "seed 0, run 2")}'
                         f'{clip("seed", v, c, "seed 1")}</div>'
                         f'<p class="meta">Seed 0 twice: {same_audio(v, a, b)}</p></div>')
sections.append(f"""<section><h2>3. Does a fixed seed repeat a line?</h2>
<p>A regenerated line should sound like the old one. Each line was rendered twice with seed 0 and once with seed 1.</p>
{''.join(seed_rows)}
<label>Is the seed 1 take different enough to matter? Should a regenerated line keep its seed?
<textarea data-k="seed"></textarea></label></section>""")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Emotion Settings Test</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6b66;--line:#ddddd8;--card:#fff;--bad:#b3261e;--accent:#2f5d8a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1a;--fg:#ececea;--muted:#9a9a94;--line:#3a3a37;--card:#242423;
--bad:#f2867e;--accent:#8fb6dd}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}}
section{{border-top:1px solid var(--line);margin-top:24px}}h1{{margin-bottom:0}}h3{{margin:20px 0 4px}}h4{{margin:4px 0}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}}
.clip{{margin:4px 0}}.lab{{font-size:13px}}.meta{{color:var(--muted);font-size:12px}}.bad{{color:var(--bad)}}
.missing{{color:var(--muted);font-size:13px}}audio{{width:100%;max-width:320px;height:32px}}
.voices{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.voice,.emo{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0}}
.verdict{{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:8px;font-size:13px}}.text{{font-style:italic}}
textarea{{width:100%;height:70px;font:inherit;box-sizing:border-box}}input{{font:inherit;width:240px}}
button{{font:inherit;padding:6px 12px}}#out{{height:160px;font:12px/1.4 monospace}}
</style></head><body>
<h1>Emotion settings for Chatterbox 500M</h1>
<p class="meta">PROTOTYPE, throwaway. Ticket 16. Voices from the built-in library: {", ".join(VOICES)}.
Your answers are kept in this browser; when done, press the button and paste the result back to Claude.</p>
{''.join(sections)}
<section><h2>Your verdicts</h2><button id="copy">Copy my verdicts</button>
<textarea id="out" readonly></textarea></section>
<script>
const KEY="chorus-ticket16";let saved={{}};try{{saved=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{}}
const fields=[...document.querySelectorAll("[data-k]")];
function dump(){{const o={{}};fields.forEach(f=>{{if(f.value)o[f.dataset.k]=f.value}});
document.getElementById("out").value=JSON.stringify(o,null,1);try{{localStorage.setItem(KEY,JSON.stringify(o))}}catch(e){{}}}}
fields.forEach(f=>{{if(saved[f.dataset.k])f.value=saved[f.dataset.k];f.addEventListener("input",dump);f.addEventListener("change",dump)}});
dump();
document.getElementById("copy").onclick=()=>{{const t=document.getElementById("out");t.select();
navigator.clipboard?navigator.clipboard.writeText(t.value):document.execCommand("copy")}};
// one clip at a time
document.addEventListener("play",e=>document.querySelectorAll("audio").forEach(a=>{{if(a!==e.target)a.pause()}}),true);
</script></body></html>"""
(ROOT / "listen.html").write_text(page, encoding="utf-8")
print("wrote listen.html")
