"""PROTOTYPE, throwaway. Build compare.html: every approach's Script for every sample passage, side by side.
Quotes where the approaches disagree on the Speaker are highlighted, with a verdict picker per line.
Run with any Python 3: python compare.py"""
import html, json, pathlib, re
from score import GOLD, person

ROOT = pathlib.Path(__file__).parent
approaches = sorted(p.name for p in (ROOT / "scripts").iterdir() if p.is_dir())
esc = html.escape


def norm(s):
    return re.sub(r"^(the|a|an) ", "", re.sub(r"[^a-z ]", "", s.lower().replace("mister", "mr")).strip())


def keys(script, speaker):
    """Every normalised name this approach uses for a Speaker, so differently spelled names still match."""
    out = {norm(speaker)}
    for c in script.get("characters", []):
        if norm(c["name"]) == norm(speaker):
            out |= {norm(a) for a in c.get("aliases", [])}
    return out - {""}


sections, summary = [], []
for f in sorted((ROOT / "lines").glob("*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    scripts = {}
    for a in approaches:
        p = ROOT / "scripts" / a / f.name
        if p.exists():
            scripts[a] = json.loads(p.read_text(encoding="utf-8"))
    if not scripts:
        continue
    names = list(scripts)
    rows, quotes, spk_dis, emo_dis = [], 0, 0, 0
    gold, wrong = GOLD[data['passage']], {a: 0 for a in names}
    for l in data["lines"]:
        if l["kind"] != "quote":
            rows.append(f"<tr class='narr'><td class='id'></td><td colspan='{len(names) + 3}'>{esc(l['text'])}</td></tr>")
            continue
        quotes += 1
        labs = [scripts[a]["labels"].get(str(l["id"])) for a in names]
        present = [(a, x) for a, x in zip(names, labs) if x]
        key_sets = [keys(scripts[a], x["speaker"]) for a, x in present]
        ok = [bool(x) and person(data['passage'], x['speaker']) in gold[l['id']] for x in labs]
        for a, good in zip(names, ok):
            wrong[a] += not good
        differ = not all(ok) or len(present) < len(names) or any(not (key_sets[0] & k) for k in key_sets[1:])
        emo_differ = len({x["emotion"] for _, x in present}) > 1
        spk_dis += differ
        emo_dis += emo_differ and not differ
        cells = "".join(
            f"<td class='lab{'' if good else ' wrong'}'>{'<b>' + esc(x['speaker']) + '</b><br><span class=emo>' + esc(x['emotion']) + ' · ' + esc(x['intensity']) + (' · ' + esc(x['kind']) if x['kind'] != 'speech' else '') + '</span>' if x else '<span class=miss>no label</span>'}</td>"
            for x, good in zip(labs, ok))
        cells += f"<td class='ref'>{esc(' or '.join(gold[l['id']]))}</td>"
        verdict = ""
        if differ:
            opts = "".join(f"<option>{esc(a)}</option>" for a in names)
            verdict = f"<select class='verdict' data-passage='{esc(data['passage'])}' data-id='{l['id']}'><option value=''>who is right?</option><option>the reference</option>{opts}<option>none of them</option><option>unclear in the text</option></select>"
        rows.append(f"<tr class='q{' differ' if differ else ''}{' emodiff' if emo_differ and not differ else ''}'><td class='id'>{l['id']}</td>"
                    f"<td class='text'>{esc(l['text'])}</td>{cells}<td>{verdict}</td></tr>")
    casts = "".join(
        f"<div class='cast'><h4>{esc(a)}</h4><p class='meta'>Narration: {esc(s['narrator']['person'])} person"
        f"{' (' + esc(s['narrator']['character']) + ')' if s['narrator'].get('character') else ''} · {s['seconds']} s · "
        f"{len(s.get('missing', []))} quotes unlabelled</p><ul>"
        + "".join(f"<li><b>{esc(c['name'])}</b> ({esc(c.get('gender', '?'))}, {esc(c.get('age', '?'))})"
                  f"{': ' + esc(', '.join(c['aliases'])) if c.get('aliases') else ''}</li>" for c in s["characters"])
        + "</ul><p class='meta'>Scenes: "
        + "; ".join(f"from paragraph {sc['first_paragraph']}: {esc(sc['setting'])} ({esc(sc['mood'])})" for sc in s.get("scenes", []))
        + "</p></div>" for a, s in scripts.items())
    head = "".join(f"<th>{esc(a)}</th>" for a in names)
    sections.append(f"<section><h2>{esc(data['title'])}</h2><p class='meta'>{quotes} quotes · wrong Speaker by the reference: "
                    f"{', '.join(f'{esc(a)} {wrong[a]}' for a in names)} · highlighted rows {spk_dis} · same Speaker but different Emotion on {emo_dis}</p><div class='casts'>{casts}</div>"
                    f"<div class='tablewrap'><table><tr><th></th><th>Text</th>{head}<th>Claude's reference</th><th>Your verdict</th></tr>{''.join(rows)}</table></div></section>")
    summary.append(f"<tr><td>{esc(data['passage'])}</td><td>{quotes}</td>" + "".join(f"<td>{wrong[a]}</td>" for a in names) + f"<td>{emo_dis}</td>"
                   + "".join(f"<td>{s['seconds']} s</td>" for s in scripts.values()) + "</tr>")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Attribution Approaches</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e1dc;--hi:#fff3bf;--emo:#3b5bdb;--bad:#c92a2a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--muted:#9c9b95;--card:#20201e;--line:#34332f;--hi:#4a3f12;--emo:#91a7ff;--bad:#ff8787}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1300px;padding:16px 16px 110px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
.tablewrap{{overflow-x:auto}}.narr td{{color:var(--muted);font-size:13px}}.differ{{background:var(--hi)}}.emodiff .emo{{font-weight:600}}
.id,.meta{{color:var(--muted);font-size:13px}}.emo{{color:var(--emo);font-size:13px}}.miss{{color:var(--bad)}}.wrong b{{color:var(--bad)}}.ref{{color:var(--muted);font-size:13px}}.lab{{min-width:150px}}
.casts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}.cast{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:4px 14px}}
.cast ul{{margin:4px 0;padding-left:18px;font-size:14px}}h4{{margin:8px 0 0}}body.only .q:not(.differ),body.only .narr{{display:none}}
#bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
button,select{{font:inherit}}button{{padding:6px 12px}}textarea{{width:100%;height:140px;font:12px/1.4 monospace}}
</style></head><body>
<h1>Speaker attribution and Emotion: approaches side by side</h1>
<p>PROTOTYPE for ticket 08. The same six sample passages, labelled by each approach. Narration is grey. <b>a-booknlp-llm</b>
takes the Speaker from BookNLP where a quote has a speech tag in its own paragraph and from the language model elsewhere;
<b>b-llm-only</b> uses the language model for everything. The reference column is Claude's own reading of the text, not
yours: a Speaker in red disagrees with it. A row is highlighted where the approaches disagree with each other or with the
reference; for those, pick who is right if you disagree with the reference, then press <b>Copy my verdicts</b> and paste
the result to Claude. Also look at the Emotion under each Speaker. Nothing is saved if you reload.</p>
<div class="tablewrap"><table><tr><th>Passage</th><th>Quotes</th>{''.join(f'<th>{esc(a)} wrong Speakers</th>' for a in approaches)}<th>Emotion differs only</th>{''.join(f'<th>{esc(a)} time</th>' for a in approaches)}</tr>{''.join(summary)}</table></div>
{''.join(sections)}
<div id="result"></div>
<div id="bar"><label><input type="checkbox" id="only"> Show only disagreements</label><span id="count"></span><button id="copy">Copy my verdicts</button><span id="msg" class="meta"></span></div>
<script>
const sel=[...document.querySelectorAll('.verdict')];
function state(){{return sel.filter(s=>s.value).map(s=>({{passage:s.dataset.passage,id:+s.dataset.id,right:s.value}}));}}
function refresh(){{document.getElementById('count').textContent=state().length+' of '+sel.length+' disagreements judged';}}
document.addEventListener('change',refresh);refresh();
document.getElementById('only').onchange=e=>document.body.classList.toggle('only',e.target.checked);
document.getElementById('copy').onclick=()=>{{const t=JSON.stringify(state());
 document.getElementById('result').innerHTML='<h2>Your verdicts</h2><textarea readonly></textarea>';
 const ta=document.querySelector('textarea');ta.value=t;ta.scrollIntoView();
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>document.getElementById('msg').textContent='Copied to clipboard.',
 ()=>document.getElementById('msg').textContent='Select the text above and copy it.');}};
</script></body></html>"""
(ROOT / "compare.html").write_text(page, encoding="utf-8")
print("wrote compare.html with approaches", approaches)
