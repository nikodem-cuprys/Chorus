"""PROTOTYPE, throwaway. Build listen.html: every Script line x every model, side by side,
with a blind mode (shuffled, unlabeled columns) and the measured VRAM/speed table.
Run with any Python 3: python build_page.py"""
import html, json, pathlib

ROOT = pathlib.Path(__file__).parent
SCRIPT = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
models = []
for d in sorted((ROOT / "out").glob("*/metrics.json")):
    m = json.loads(d.read_text(encoding="utf-8"))
    m["dir"] = d.parent.name
    models.append(m)

def cell(v, unit=""):
    return "-" if v is None else f"{v}{unit}"

rows = "".join(
    f"<tr><td>{html.escape(m['model'])}</td><td>{html.escape(m.get('device_note', ''))}</td><td>{m['torch']}</td>"
    f"<td>{cell(m.get('load_s'), ' s')}</td><td>{cell(m.get('vram_after_load_mib'), ' MiB')}</td>"
    f"<td>{cell(m.get('torch_peak_reserved_mib'), ' MiB')}</td><td>{cell(m.get('card_peak_mib'), ' MiB')}</td>"
    f"<td>{cell(m.get('mean_rtf'))}</td><td>{sum('error' in l for l in m['lines'])}</td></tr>" for m in models)

lines_html = []
for line in SCRIPT["lines"]:
    spk = SCRIPT["speakers"][line["speaker"]]
    players = []
    for m in models:
        rec = next((l for l in m["lines"] if l["id"] == line["id"]), {})
        if "error" in rec or not (ROOT / "out" / m["dir"] / f"{line['id']}.wav").exists():
            body = f"<div class='err'>failed: {html.escape(rec.get('error', 'missing'))[:200]}</div>"
        else:
            body = (f"<audio controls preload='none' src='out/{m['dir']}/{line['id']}.wav'></audio>"
                    f"<div class='meta'>RTF {rec.get('rtf')} · {rec.get('audio_s')} s</div>")
        players.append(f"<div class='player' data-model='{html.escape(m['model'])}'>"
                       f"<div class='label'>{html.escape(m['model'])}</div>{body}"
                       f"<select class='score'><option value=''>score</option>"
                       + "".join(f"<option>{i}</option>" for i in range(1, 6)) + "</select></div>")
    lines_html.append(
        f"<section class='line' data-id='{line['id']}'><h3>{line['id']} · {html.escape(line['speaker'])} · "
        f"<span class='emo'>{html.escape(line['emotion'])}</span></h3><p class='text'>{html.escape(line['text'])}</p>"
        f"<p class='spk'>{html.escape(spk['desc'])} · <a href='{spk['ref']}'>reference clip</a></p>"
        f"<div class='players'>{''.join(players)}</div></section>")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Voice Listening Test</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e1dc;--err:#b3261e;--accent:#3b5bdb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--muted:#9c9b95;--card:#20201e;--line:#34332f;--err:#f28b82;--accent:#91a7ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1200px;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid var(--line);padding:6px;text-align:left}}
.tablewrap{{overflow-x:auto}}.line{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:16px 0}}
.text{{font-style:italic}}.spk,.meta{{color:var(--muted);font-size:13px}}.emo{{color:var(--accent)}}
.players{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}
.player{{border:1px solid var(--line);border-radius:6px;padding:8px}}audio{{width:100%}}.label{{font-weight:600}}
.err{{color:var(--err);font-size:13px}}body.blind .label{{visibility:hidden}}button{{font:inherit;padding:6px 12px}}
</style></head><body>
<h1>Voice listening test</h1>
<p>PROTOTYPE for the ticket "Listening test of the top voice candidates on the 1050 Ti". Same eight Script lines, every model.
Each Character's Voice is cloned from its reference clip. Score each take 1-5; <b>Show results</b> sums scores per model.</p>
<p><button id="blind">Blind mode: off</button> <button id="results">Show results</button></p>
<div id="summary"></div>
<h2>Measured on this machine</h2>
<div class="tablewrap"><table><tr><th>Model</th><th>Setup</th><th>torch</th><th>Load</th><th>VRAM after load</th>
<th>Torch peak reserved</th><th>Whole-card peak (incl. desktop)</th><th>Mean RTF (lower = faster)</th><th>Failed lines</th></tr>{rows}</table></div>
<p class="meta">RTF = generation time ÷ audio length. RTF 2 means one minute of audio takes two minutes.</p>
{''.join(lines_html)}
<script>
const blindBtn=document.getElementById('blind');
blindBtn.onclick=()=>{{const on=document.body.classList.toggle('blind');blindBtn.textContent='Blind mode: '+(on?'on':'off');
 document.querySelectorAll('.players').forEach(p=>{{const k=[...p.children];k.sort(()=>Math.random()-.5).forEach(c=>p.appendChild(c));}});}};
document.getElementById('results').onclick=()=>{{const t={{}};document.querySelectorAll('.player').forEach(p=>{{
 const v=+p.querySelector('.score').value;const m=p.dataset.model;t[m]=t[m]||{{s:0,n:0}};if(v){{t[m].s+=v;t[m].n++;}}}});
 document.getElementById('summary').innerHTML='<h2>Your scores</h2><ul>'+Object.entries(t).sort((a,b)=>b[1].s-a[1].s)
 .map(([m,x])=>'<li><b>'+m+'</b>: '+x.s+' points over '+x.n+' takes'+(x.n?' (avg '+(x.s/x.n).toFixed(2)+')':'')+'</li>').join('')+'</ul>';}};
</script></body></html>"""
(ROOT / "listen.html").write_text(page, encoding="utf-8")
print("wrote", ROOT / "listen.html", "with", len(models), "models")
