"""PROTOTYPE, throwaway (ticket 19). Build listen.html from the clips gen.py rendered.
Run with any Python 3: python build_page.py"""
import html, json, pathlib
from gen import NAMES, RUNS, SENTENCE, STYLES, slug

ROOT = pathlib.Path(__file__).parent
LABEL = {"written": "as written", "hyphen": "respelled with hyphens", "fused": "respelled as one word"}


def clip(name, style, voice, seed):
    key = f"{slug(name)}_{style}_{voice}_s{seed}"
    if not (ROOT / "out" / f"{key}.json").exists():
        return '<td class="missing">not rendered yet</td>'
    return f'<td><audio controls preload="none" src="out/{key}.wav"></audio></td>'


def sel(key, options):
    return f'<select data-k="{key}"><option value="">-</option>' + "".join(f"<option>{o}</option>" for o in options) + "</select>"


blocks = []
for name, (target, hyphen, fused) in NAMES.items():
    rows = ""
    for style, spoken in zip(STYLES, (name, hyphen, fused)):
        k = f"{slug(name)}.{style}"
        rows += (f'<tr><th>{LABEL[style]}<br><span class="spoken">{html.escape(spoken)}</span></th>'
                 + "".join(clip(name, style, v, s) for v, s in RUNS)
                 + f'<td class="verdict"><label>Name said right? {sel(k + ".right", ["every time", "some clips only", "close but off", "wrong"])}</label>'
                 f'<label>Sounds natural in the sentence? {sel(k + ".natural", ["yes", "odd pause or stress", "no"])}</label></td></tr>')
    blocks.append(f'<div class="emo"><h3>{html.escape(name)} <span class="meta">should sound like: {html.escape(target)}</span></h3>'
                  f'<table><tr><th></th>' + "".join(f"<th>{v}, take {s + 1}</th>" for v, s in RUNS)
                  + f'<th>Your verdict</th></tr>{rows}</table>'
                  f'<label>Notes <input data-k="{slug(name)}.notes"></label></div>')

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Name Pronunciation Test</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#6b6b66;--line:#ddddd8;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1a;--fg:#ececea;--muted:#9a9a94;--line:#3a3a37;--card:#242423}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}}
section{{border-top:1px solid var(--line);margin-top:24px}}h1{{margin-bottom:0}}h3{{margin:4px 0}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid var(--line);padding:6px;text-align:left;vertical-align:top;font-weight:normal;font-size:13px}}
.meta{{color:var(--muted);font-size:13px;font-weight:normal}}.spoken{{font-weight:600;font-size:15px}}
.missing{{color:var(--muted)}}audio{{width:190px;height:32px}}
.emo{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:12px 0}}
.verdict label{{display:block;margin:2px 0}}.overall label{{display:block;margin:8px 0}}
textarea{{width:100%;height:70px;font:inherit;box-sizing:border-box}}input{{font:inherit;width:320px}}
button{{font:inherit;padding:6px 12px}}#out{{height:160px;font:12px/1.4 monospace}}
</style></head><body>
<h1>Can a respelling fix how a name is said?</h1>
<p class="meta">PROTOTYPE, throwaway. Ticket 19. Every clip says: "{html.escape(SENTENCE.format(n="NAME"))}" so the name
is heard twice. Each row is one way of writing the name; the three clips in a row are the same text with a different
Voice or take, to show whether it comes out the same every time. The "should sound like" line is Claude's reading of the
usual pronunciation; say in the notes if it is wrong. Your answers are kept in this browser; when done, press the
button and paste the result back to Claude.</p>
{''.join(blocks)}
<section class="overall"><h2>Overall</h2>
<label>Does respelling fix names well enough to build the lexicon on it? {sel("overall.works", ["yes", "mostly, with some names it cannot fix", "too unreliable"])}</label>
<label>Which way of respelling works better? {sel("overall.style", ["with hyphens", "as one word", "no real difference", "depends on the name"])}</label>
<label>Did the same text come out differently between takes or Voices? {sel("overall.stable", ["no, it was consistent", "sometimes", "often"])}</label>
<label>Anything else <textarea data-k="overall.notes"></textarea></label></section>
<section><h2>Your verdicts</h2><button id="copy">Copy my verdicts</button>
<textarea id="out" readonly></textarea></section>
<script>
const KEY="chorus-ticket19";let saved={{}};try{{saved=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{}}
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
print("wrote listen.html")
