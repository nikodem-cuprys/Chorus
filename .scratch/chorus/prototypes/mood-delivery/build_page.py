"""PROTOTYPE, throwaway (ticket 17). Assemble each Scene per Mood from the clips gen.py rendered and build
listen.html. Per Mood there are three mixes: pauses only, Narrator delivery only, and both; plus one mix with
Mood ignored. The four full mixes are also copied under neutral names for a blind guess.
Run with the frozen-stack env: python build_page.py"""
import html, json, pathlib, random
import numpy as np, soundfile as sf, librosa
from gen import MOODS, PAUSE, SCENES, N

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
SR = 24000
LEAD = 0.4


def load(scene, key):
    f = OUT / scene / "clips" / f"{key}.wav"
    if not f.exists():
        return None
    y, sr = sf.read(f, dtype="float32")
    assert sr == SR
    y, _ = librosa.effects.trim(y, top_db=35)  # so the pauses are the ones set here
    return y


def mix(scene, narrator_mood, pause_mood):
    """Returns (audio, stats) or None if a clip is missing."""
    parts, speech, pauses, narr = [np.zeros(int(LEAD * SR), dtype=np.float32)], 0.0, 0.0, [0.0, 0]
    for i, (spk, _, _, text, after) in enumerate(SCENES[scene]["lines"]):
        y = load(scene, f"{i:02d}_{narrator_mood}" if spk == N else f"{i:02d}")
        if y is None:
            return None
        gap = PAUSE[after] * MOODS[pause_mood]["pause"]
        parts += [y, np.zeros(int(gap * SR), dtype=np.float32)]
        speech += len(y) / SR
        pauses += gap
        if spk == N:
            narr[0] += len(y) / SR
            narr[1] += len(text.split())
    return np.concatenate(parts), dict(total=speech + pauses + LEAD, pauses=pauses, narrator_wps=narr[1] / narr[0])


def audio(scene, name, label, stats):
    meta = (f'<span class="meta">{stats["total"]:.0f} s · pauses {stats["pauses"]:.1f} s · '
            f'Narrator {stats["narrator_wps"]:.2f} words/s</span>') if stats else ""
    return (f'<div class="clip"><div class="lab">{html.escape(label)} {meta}</div>'
            f'<audio controls preload="none" src="out/{scene}/mix/{name}.wav"></audio></div>')


def sel(key, options):
    return f'<select data-k="{key}"><option value="">-</option>' + "".join(f"<option>{o}</option>" for o in options) + "</select>"


real = [m for m in MOODS if m != "calm"]
sections, missing = [], False
for scene, s in SCENES.items():
    (OUT / scene / "mix").mkdir(parents=True, exist_ok=True)
    made = {}
    todo = [("ignored", "calm", "calm")]
    for m in real:
        todo += [(f"{m}_pauses", "calm", m), (f"{m}_narrator", m, "calm"), (f"{m}_both", m, m)]
    for name, nm, pm in todo:
        r = mix(scene, nm, pm)
        if r is None:
            missing = True
            continue
        sf.write(OUT / scene / "mix" / f"{name}.wav", r[0], SR)
        made[name] = r[1]
    script = "".join(f'<p><b>{html.escape(spk)}</b>{"" if spk == N else f" <span class=meta>({emo}, {inten})</span>"}: '
                     f'{html.escape(text)}</p>' for spk, emo, inten, text, _ in s["lines"])
    if len(made) < len(todo):
        sections.append(f'<section><h2>{html.escape(s["title"])}</h2><p class="missing">not rendered yet</p></section>')
        continue
    # blind: the four full mixes under neutral names, in a fixed shuffled order
    full = ["ignored"] + [f"{m}_both" for m in real]
    random.Random(scene).shuffle(full)
    blind, key = [], []
    for letter, name in zip("ABCD", full):
        y, _ = sf.read(OUT / scene / "mix" / f"{name}.wav", dtype="float32")
        sf.write(OUT / scene / "mix" / f"blind_{letter}.wav", y, SR)
        blind.append(f'<div class="voice">{audio(scene, f"blind_{letter}", f"Version {letter}", None)}'
                     f'<label>Which Mood is this? {sel(f"{scene}.blind.{letter}", ["calm (no Mood)"] + real + ["cannot tell"])}</label></div>')
        key.append(f"{letter} = {'calm (Mood ignored)' if name == 'ignored' else name.split('_')[0]}")
    rows = "".join(
        f'<tr><th>{m}<br><span class="meta">Narrator ex {MOODS[m]["narrator"][0]} · cfg {MOODS[m]["narrator"][1]}<br>'
        f'pauses × {MOODS[m]["pause"]}</span></th>'
        + "".join(f'<td>{audio(scene, f"{m}_{v}", lab, made[f"{m}_{v}"])}</td>'
                  for v, lab in (("pauses", "pauses only"), ("narrator", "Narrator delivery only"), ("both", "both")))
        + f'<td class="verdict"><label>Different from Mood ignored? {sel(f"{scene}.{m}.different", ["clearly", "slightly", "no"])}</label>'
          f'<label>Fits the Mood? {sel(f"{scene}.{m}.fits", ["yes", "somewhat", "no"])}</label>'
          f'<label>What does the work? {sel(f"{scene}.{m}.work", ["pauses", "Narrator delivery", "both", "neither"])}</label>'
          f'<label>Notes <input data-k="{scene}.{m}.notes"></label></td></tr>' for m in real)
    sections.append(f"""<section><h2>{html.escape(s["title"])}</h2>
<details><summary>The Scene's lines</summary>{script}</details>
<h3>1. Blind: guess the Mood</h3>
<p>The same Scene four times: once with Mood ignored and once each as {", ".join(real)}. Character lines are identical
in all four; only the Narrator's delivery and the pauses change. Guess before opening the next part.</p>
<div class="voices">{"".join(blind)}</div>
<details><summary>2. Open after guessing: the answers, and what each part does</summary>
<p><b>Answers:</b> {" · ".join(key)}</p>
{audio(scene, "ignored", "Mood ignored (Narrator ex 0.5 · cfg 0.5, pauses × 1)", made["ignored"])}
<table><tr><th>Mood</th><th>pauses only</th><th>Narrator delivery only</th><th>both</th><th>Your verdict</th></tr>{rows}</table>
</details></section>""")

sections.append(f"""<section><h2>Overall</h2><div class="verdict">
<label>Can a listener hear a Scene's Mood this way? {sel("overall.audible", ["yes, clearly", "only some Moods", "barely", "no"])}</label>
<label>What should Mood do in Chorus? {sel("overall.decision", ["change Narrator delivery and pauses", "change pauses only", "change Narrator delivery only", "stay in the Script but change nothing in the audio", "drop Mood from the Script"])}</label></div>
<label>Which Moods are worth keeping, and which sound the same? <textarea data-k="overall.list"></textarea></label>
<label>Anything that sounded wrong (pauses too long or short, Narrator overacting)? <textarea data-k="overall.notes"></textarea></label>
</section>""")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mood Delivery Test</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6b66;--line:#ddddd8;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1a;--fg:#ececea;--muted:#9a9a94;--line:#3a3a37;--card:#242423}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}}
section{{border-top:1px solid var(--line);margin-top:24px}}h1{{margin-bottom:0}}h3{{margin:20px 0 4px}}
table{{border-collapse:collapse;width:100%;margin-top:8px}}td,th{{border:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}}
.clip{{margin:4px 0}}.lab{{font-size:13px}}.meta{{color:var(--muted);font-size:12px;font-weight:normal}}
.missing{{color:var(--muted)}}audio{{width:100%;max-width:300px;height:32px}}
.voices{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
.voice{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px}}
.verdict{{font-size:13px}}.verdict label,.voice label{{display:block;margin:4px 0}}
details{{margin:8px 0}}summary{{cursor:pointer;font-weight:600}}details p{{margin:4px 0}}
textarea{{width:100%;height:70px;font:inherit;box-sizing:border-box}}input{{font:inherit;width:200px}}
button{{font:inherit;padding:6px 12px}}#out{{height:160px;font:12px/1.4 monospace}}
</style></head><body>
<h1>Can you hear a Scene's Mood without music?</h1>
<p class="meta">PROTOTYPE, throwaway. Ticket 17. Narrator: af_bella. Character lines use the ticket 16 Emotion settings
and never change. Your answers are kept in this browser; when done, press the button and paste the result back to Claude.</p>
{''.join(sections)}
<section><h2>Your verdicts</h2><button id="copy">Copy my verdicts</button>
<textarea id="out" readonly></textarea></section>
<script>
const KEY="chorus-ticket17";let saved={{}};try{{saved=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{}}
const fields=[...document.querySelectorAll("[data-k]")];
function dump(){{const o={{}};fields.forEach(f=>{{if(f.value)o[f.dataset.k]=f.value}});
document.getElementById("out").value=JSON.stringify(o,null,1);try{{localStorage.setItem(KEY,JSON.stringify(o))}}catch(e){{}}}}
fields.forEach(f=>{{if(saved[f.dataset.k])f.value=saved[f.dataset.k];f.addEventListener("input",dump);f.addEventListener("change",dump)}});
dump();
document.getElementById("copy").onclick=()=>{{const t=document.getElementById("out");t.select();
navigator.clipboard?navigator.clipboard.writeText(t.value):document.execCommand("copy")}};
document.addEventListener("play",e=>document.querySelectorAll("audio").forEach(a=>{{if(a!==e.target)a.pause()}}),true);
</script></body></html>"""
(ROOT / "listen.html").write_text(page, encoding="utf-8")
print("wrote listen.html" + (" (some clips missing)" if missing else ""))
