"""PROTOTYPE, throwaway. Shortlist 12 Kokoro voices for contrast and build listen.html.
Contrast = distance between the speaker embeddings Chatterbox derives from each reference clip.
Run with the frozen-stack env after gen_clones.py: python build_page.py"""
import html, itertools, json, pathlib, re
import numpy as np, librosa

ROOT = pathlib.Path(__file__).parent
LINES = json.loads((ROOT / "lines.json").read_text(encoding="utf-8"))
REF_TEXT = (ROOT / "refs" / "_text.txt").read_text(encoding="utf-8")
GRADE_POINTS = {"A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7,
                "D+": 1.3, "D": 1.0, "D-": 0.7, "F+": 0.3, "F": 0.0}
FORCED = {"bf_isabella"}   # best Voice in the model listening test
EXCLUDED = {"am_santa"}    # novelty voice
TIMBRE_WORDS = ["low", "high", "bright", "dark", "brisk", "measured", "warm", "soft", "gruff", "crisp"]

grades = {}
for row in (ROOT / "kokoro-voices" / "VOICES.md").read_text(encoding="utf-8").splitlines():
    m = re.match(r"\|\s*\**([ab][fm])\\?_([a-z]+)\**\s*\|", row)
    if m:
        cols = [c.strip().strip("*") for c in row.strip("|").split("|")]
        grades[f"{m[1]}_{m[2]}"] = cols[4]

voices = {}
for f in sorted((ROOT / "out").glob("*/info.json")):
    info = json.loads(f.read_text(encoding="utf-8"))
    name = info["voice"]
    cache = f.parent / "measure.json"
    if cache.exists():
        meas = json.loads(cache.read_text(encoding="utf-8"))
    else:
        y, sr = librosa.load(f.parent / "narration.wav", sr=None)
        f0, _, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr)
        meas = {"pitch_hz": round(float(np.nanmedian(f0))),
                "centroid_hz": round(float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())),
                "words_per_s": round(len(LINES["narration"]["text"].split()) / (len(y) / sr), 2)}
        cache.write_text(json.dumps(meas), encoding="utf-8")
    e = np.array(info["speaker_emb"])
    e /= np.linalg.norm(e)
    voices[name] = dict(name=name, gender="female" if name[1] == "f" else "male",
                        accent="American" if name[0] == "a" else "British", grade=grades.get(name, "?"),
                        emb=e, lines=info["lines"], **meas)

names = sorted(voices)
dist = {a: {b: float(1 - voices[a]["emb"] @ voices[b]["emb"]) for b in names} for a in names}


def pick(gender, k=6):
    pool = [n for n in names if voices[n]["gender"] == gender and n not in EXCLUDED]
    best, best_score = None, -1
    for combo in itertools.combinations(pool, k):
        if not (FORCED & set(pool)) <= set(combo):
            continue
        accents = [voices[n]["accent"] for n in combo]
        if accents.count("British") < 2 or accents.count("American") < 2:
            continue
        pairs = [dist[a][b] for a, b in itertools.combinations(combo, 2)]
        score = (min(pairs) + 0.25 * np.mean(pairs)
                 + 0.02 * np.mean([GRADE_POINTS.get(voices[n]["grade"], 1) for n in combo]))
        if score > best_score:
            best, best_score = combo, score
    return set(best or [])


shortlist = (pick("female") | pick("male")) if len(names) >= 12 else set()
for g in ("female", "male"):  # measured, provisional timbre words: thirds within each gender
    grp = [voices[n] for n in names if voices[n]["gender"] == g]
    for v in grp:
        v["timbre"] = []
    if not grp:
        continue
    for key, lo, hi in (("pitch_hz", "low", "high"), ("centroid_hz", "dark", "bright"), ("words_per_s", "measured", "brisk")):
        a, b = np.percentile([v[key] for v in grp], [33, 67])
        for v in grp:
            if v[key] <= a:
                v["timbre"].append(lo)
            elif v[key] >= b:
                v["timbre"].append(hi)
narr_default = max(sorted(shortlist), key=lambda n: GRADE_POINTS.get(voices[n]["grade"], 0)) if shortlist else None
narr_ok = {n for n in shortlist if GRADE_POINTS.get(voices[n]["grade"], 0) >= 2.3}


def card(v):
    n = v["name"]
    near = min((o for o in names if o != n and voices[o]["gender"] == v["gender"]), key=lambda o: dist[n][o], default=None)
    near_txt = f"most similar: {near} (distance {dist[n][near]:.2f})" if near else ""
    words = "".join(f'<label><input type="checkbox" class="tw" value="{w}"{" checked" if w in v["timbre"] else ""}>{w}</label>'
                    for w in TIMBRE_WORDS)
    short = n in shortlist
    return f"""<section class="voice" data-voice="{n}" data-gender="{v['gender']}" data-accent="{v['accent']}">
<h3>{n} <span class="tag">{v['accent']}</span> <span class="tag">Kokoro grade {html.escape(v['grade'])}</span>{'<span class="tag pick">shortlisted</span>' if short else ''}</h3>
<p class="meta">pitch {v['pitch_hz']} Hz · brightness {v['centroid_hz']} Hz · {v['words_per_s']} words/s · {near_txt}</p>
<div class="players">
<div><div class="label">Narration (cloned)</div><audio controls preload="none" src="out/{n}/narration.wav"></audio></div>
<div><div class="label">Dialogue, angry (cloned)</div><audio controls preload="none" src="out/{n}/dialogue.wav"></audio></div>
<div><div class="label">Kokoro reference clip</div><audio controls preload="none" src="refs/{n}.wav"></audio></div>
</div>
<div class="controls">
<label class="keep"><input type="checkbox" class="k"{' checked' if short else ''}> Keep in the 12</label>
<label><input type="checkbox" class="ns"{' checked' if n in narr_ok else ''}> Suits the Narrator</label>
<label><input type="radio" name="narrator" class="nd"{' checked' if n == narr_default else ''}> Default Narrator</label>
<label>Age <select class="age"><option>adult</option><option>young adult</option></select></label>
</div><div class="controls words">Timbre: {words}</div></section>"""


def group(gender):
    vs = sorted((v for v in voices.values() if v["gender"] == gender), key=lambda v: (v["name"] not in shortlist, v["name"]))
    return f"<h2>{'Women' if gender == 'female' else 'Men'} ({len(vs)})</h2>" + "".join(card(v) for v in vs)


page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Choose the 12 Voices</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e1dc;--accent:#3b5bdb;--pick:#2b8a3e;--bad:#c92a2a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--muted:#9c9b95;--card:#20201e;--line:#34332f;--accent:#91a7ff;--pick:#69db7c;--bad:#ff8787}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px 16px 120px}}
.voice{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin:12px 0}}
.voice.kept{{border-color:var(--pick)}}h3{{margin:4px 0}}.meta,.label{{color:var(--muted);font-size:13px}}
.tag{{font-size:12px;font-weight:400;border:1px solid var(--line);border-radius:10px;padding:1px 8px;margin-left:6px}}.tag.pick{{color:var(--pick);border-color:var(--pick)}}
.players{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}}audio{{width:100%}}
.controls{{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:8px;font-size:14px}}.keep{{font-weight:600}}.words label{{color:var(--muted)}}
#bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
button{{font:inherit;padding:6px 12px}}textarea{{width:100%;height:160px;font:12px/1.4 monospace}}.bad{{color:var(--bad)}}.text{{font-style:italic}}
</style></head><body>
<h1>Choose the 12 built-in Voices</h1>
<p>PROTOTYPE for ticket 15. Every English Kokoro voice ({len(voices)}), cloned through Chatterbox 500M (torch 2.14.0+cu126).
Twelve are pre-ticked: 6 women and 6 men chosen so that they sound as different from each other as possible, by Chatterbox's own
measure of each voice. Untick and tick until the 12 are the ones you like, tick which suit the Narrator, pick the default Narrator,
fix the age and timbre words by ear, then press <b>Copy my choices</b> and paste the result to Claude.</p>
<p class="text">Narration: {html.escape(LINES['narration']['text'])}</p>
<p class="text">Dialogue: {html.escape(LINES['dialogue']['text'])}</p>
<p class="meta">Reference clip text: {html.escape(REF_TEXT)}<br>Timbre words are pre-ticked from measurements (low/high pitch, dark/bright,
measured/brisk pace); warm, soft, gruff and crisp can only be judged by ear. Nothing is saved if you reload the page.</p>
{group('female')}{group('male')}
<div id="result"></div>
<div id="bar"><span id="count"></span><button id="copy">Copy my choices</button><span id="msg" class="meta"></span></div>
<script>
const cards=[...document.querySelectorAll('.voice')];
function state(){{return cards.filter(c=>c.querySelector('.k').checked).map(c=>({{voice:c.dataset.voice,gender:c.dataset.gender,
 accent:c.dataset.accent,age:c.querySelector('.age').value,timbre:[...c.querySelectorAll('.tw:checked')].map(x=>x.value),
 narrator_ok:c.querySelector('.ns').checked,default_narrator:c.querySelector('.nd').checked}}));}}
function refresh(){{cards.forEach(c=>c.classList.toggle('kept',c.querySelector('.k').checked));const s=state();
 const f=s.filter(v=>v.gender=='female').length,m=s.length-f,d=s.filter(v=>v.default_narrator).length;
 document.getElementById('count').innerHTML='Kept: <b>'+s.length+'</b> ('+f+' women, '+m+' men)'+
 (s.length!=12?' <span class="bad">need 12</span>':'')+(d!=1?' <span class="bad">the default Narrator must be one of the kept Voices</span>':'');}}
document.addEventListener('change',refresh);refresh();
document.getElementById('copy').onclick=()=>{{const t=JSON.stringify(state(),null,1);
 document.getElementById('result').innerHTML='<h2>Your choices</h2><textarea readonly></textarea>';
 const ta=document.querySelector('textarea');ta.value=t;ta.scrollIntoView();
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>document.getElementById('msg').textContent='Copied to clipboard.',
 ()=>document.getElementById('msg').textContent='Select the text above and copy it.');}};
</script></body></html>"""
(ROOT / "listen.html").write_text(page, encoding="utf-8")
(ROOT / "shortlist.json").write_text(json.dumps({
    "shortlist": sorted(shortlist), "default_narrator": narr_default,
    "voices": {n: {k: v[k] for k in ("gender", "accent", "grade", "pitch_hz", "centroid_hz", "words_per_s", "timbre")}
               for n, v in voices.items()},
    "distance": dist}, indent=1), encoding="utf-8")
print("voices", len(voices), "| shortlist", sorted(shortlist), "| default narrator", narr_default)
