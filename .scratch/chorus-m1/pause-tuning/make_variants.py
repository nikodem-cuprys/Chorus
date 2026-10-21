"""Pause tuning for M1 ticket 18, part 2: real excerpts of the voiced samples with each of the
six pauses at a few lengths, and a page to listen to them side by side.

Run inside the worker container, reading its database and audio:

    docker compose exec -T worker python - < .scratch/chorus-m1/pause-tuning/make_variants.py
    docker compose cp worker:/data/pause-tuning/. .scratch/chorus-m1/pause-tuning/out/

then open `out/listen.html`. Each excerpt is built as assembly builds a chapter (chorus.assembly):
trimmed takes with the pause between them. The pause between sentences and at a verse line end
inside one take is already in the take (chorus.voicing), as a run of exact zeros, and is resized.
"""

import html
import json
import shutil
from pathlib import Path

import numpy as np
import soundfile

from chorus.assembly import pause_kinds, parts_of, trim
from chorus.db import get_sessionmaker
from chorus.models import Voice, Work
from chorus.languages import get_packs
from chorus.voicing import lines_dir, pauses, pieces

WORKS = (11, 12, 13, 14, 15, 16, 17)  # the six sample passages and the pause test
PAUSE_TEST = 17
EXAMPLES = 3  # per kind of pause
OUT = Path("/data/pause-tuning")
VARIANTS = {
    "between_sentences": [0.15, 0.3, 0.45, 0.6],
    "between_lines": [0.3, 0.45, 0.6, 0.8],
    "new_paragraph": [0.5, 0.75, 1.0, 1.3],
    "verse_line_end": [0.15, 0.3, 0.5, 0.7],
    "after_title": [1.0, 1.5, 2.0, 2.5],
    "section_break": [1.5, 2.5, 3.0, 3.5],
}
WHERE = {
    "between_sentences": "Between sentences of one line",
    "between_lines": "Between lines in one paragraph (a quotation and its narration)",
    "new_paragraph": "At a new paragraph",
    "verse_line_end": "At each line end of verse",
    "after_title": "Long pause: after the Work title and author, a chapter title",
    "section_break": "Longest pause: at a Section break",
}
# A take's own pauses are runs of exact zeros this long or longer (chorus.voicing joins
# sentences with np.zeros); Chatterbox's own silence is never exactly zero for so long.
MIN_ZEROS = 0.1
# The line before and after a pause is cut to this much, with a short fade, when longer.
CONTEXT = 8.0
FADE = 0.3
PACK = get_packs()["en"]


def load(work_id: int, line) -> tuple[np.ndarray, int]:
    audio, rate = soundfile.read(lines_dir(work_id) / line.take["file"], dtype="float32")
    return audio, rate


def trimmed(work_id: int, line) -> tuple[np.ndarray, int]:
    audio, rate = load(work_id, line)
    start, end = trim(audio, rate)
    return audio[start:end], rate


def zero_runs(audio: np.ndarray, rate: int) -> list[tuple[int, int]]:
    """Runs of exact zeros inside the take (not at its ends): the joins voicing made."""
    zero = np.concatenate([[False], audio == 0.0, [False]])
    edges = np.flatnonzero(np.diff(zero.astype(np.int8)))
    runs = list(zip(edges[::2], edges[1::2], strict=True))
    return [(a, b) for a, b in runs if b - a >= MIN_ZEROS * rate and a > 0 and b < len(audio)]


def resize_joins(audio: np.ndarray, rate: int, seconds: float) -> tuple[np.ndarray, list[int]]:
    out, position, joins, length = [], 0, [], 0
    for a, b in zero_runs(audio, rate):
        out += [audio[position:a], np.zeros(int(round(seconds * rate)), dtype=np.float32)]
        length += a - position
        joins.append(length)
        length += len(out[-1])
        position = b
    out.append(audio[position:])
    return np.concatenate(out), joins


def heard(audio: np.ndarray, rate: int, joins: list[int]) -> float:
    """The silence a listener hears at the joins: the quiet run (below -50 dB, as trimming
    uses) around each, on average."""
    quiet = np.abs(audio) <= 10 ** (-50 / 20)
    lengths = []
    for j in joins:
        a = b = min(j, len(audio) - 1)
        while a > 0 and quiet[a - 1]:
            a -= 1
        while b < len(audio) and quiet[b]:
            b += 1
        lengths.append((b - a) / rate)
    return round(float(np.mean(lengths)), 2) if lengths else 0.0


def snippet(text: str, end: bool) -> str:
    words = " ".join(text.split()).split()
    if len(words) <= 12:
        return " ".join(words)
    return "… " + " ".join(words[-10:]) if end else " ".join(words[:10]) + " …"


def find_examples(session, current: dict[str, float]) -> dict[str, list[dict]]:
    """Up to EXAMPLES places for each kind of pause, each from a different Work if possible."""
    voices = {v.id: v.name for v in session.query(Voice)}
    found: dict[str, list[dict]] = {k: [] for k in VARIANTS}
    for work_id in WORKS:
        work = session.get(Work, work_id)
        if work is None:
            continue
        parts = parts_of(session, work)
        flat = [(p, i) for p in parts for i in range(len(p.lines))]
        kinds_of = {id(p): pause_kinds(p) for p in parts}
        taken_here: set[str] = set()
        # The pause test holds the only verse and Section breaks: take all it has.
        once = work_id != PAUSE_TEST

        def ok(line) -> bool:
            # The sample files open with "#" notes about the sample, voiced like any text.
            return bool(line.take) and line.take["seconds"] >= 1.0 and not line.text.startswith("#")

        for n, (part, i) in enumerate(flat):
            line = part.lines[i]
            if not line.take or line.text.startswith("#"):
                continue
            # Inside one take: sentences, or verse line ends.
            inside = "verse_line_end" if line.passage == "verse" else "between_sentences"
            if (
                inside not in taken_here
                and len(found[inside]) < EXAMPLES
                and 3.0 <= line.take["seconds"] <= 16.0
                # Every join voicing made, and nothing else, is a run of zeros.
                and len(pieces(line, PACK, current)) >= 2
                and len(zero_runs(*load(work_id, line))) == len(pieces(line, PACK, current)) - 1
            ):
                found[inside].append({
                    "work": work_id, "title": work.title, "voice": voices.get(line.take["voice_id"]),
                    "lines": [line], "text": snippet(line.text, False),
                })  # fmt: skip
                once and taken_here.add(inside)
            # Between this line and the next one in reading order (the next part's first line
            # after the last line of a part).
            kinds = kinds_of[id(part)][i] or (["after_title"] if line.passage == "work_title" else [])
            following = flat[n + 1] if n + 1 < len(flat) else None
            if not kinds or following is None:
                continue
            nxt = following[0].lines[following[1]]
            kind = max(kinds, key=lambda k: VARIANTS[k][1])
            if kind in taken_here or len(found[kind]) >= EXAMPLES or not (ok(nxt) and line.take):
                continue
            found[kind].append({
                "work": work_id, "title": work.title, "voice": voices.get(nxt.take["voice_id"]),
                "lines": [line, nxt],
                "text": f"{snippet(line.text, True)}  ‖  {snippet(nxt.text, False)}",
            })  # fmt: skip
            once and taken_here.add(kind)
    return found


def render(example: dict, kind: str, seconds: float) -> tuple[np.ndarray, list[int]]:
    """The excerpt, and where its pauses are (sample indexes)."""
    if len(example["lines"]) == 1:
        audio, rate = trimmed(example["work"], example["lines"][0])
        return resize_joins(audio, rate, seconds)
    (a, rate), (b, _) = (trimmed(example["work"], ln) for ln in example["lines"])
    keep, fade = int(CONTEXT * rate), np.linspace(0, 1, int(FADE * rate), dtype=np.float32)
    if len(a) > keep:  # the end of a long line, faded in
        a = a[-keep:].copy()
        a[: len(fade)] *= fade
    if len(b) > keep:  # the start of a long line, faded out
        b = b[:keep].copy()
        b[-len(fade) :] *= fade[::-1]
    return np.concatenate([a, np.zeros(int(round(seconds * rate)), dtype=np.float32), b]), [len(a)]


def page(found: dict[str, list[dict]], current: dict[str, float]) -> str:
    rows = []
    for kind, examples in found.items():
        values = VARIANTS[kind]
        rows.append(f"<section><h2>{html.escape(WHERE[kind])}</h2>")
        rows.append(f"<p class=muted>Now <b>{current[kind]} s</b> (<code>{kind}</code>).</p>")
        if not examples:
            rows.append("<p class=muted>No example in the voiced passages yet.</p>")
        for n, ex in enumerate(examples):
            rows.append(
                f"<div class=example><p><b>{n + 1}.</b> {html.escape(ex['text'])}"
                f" <span class=muted>({html.escape(ex['title'])}, {ex['voice']})</span></p><div class=row>"
            )
            for v in values:
                mark = " now" if v == current[kind] else ""
                rows.append(
                    f"<figure class='v{mark}'><figcaption>{v} s{' (now)' if mark else ''}"
                    f" · heard {ex['heard'][v]} s</figcaption>"
                    f"<audio controls preload=none src='{kind}-{n + 1}-{v}.wav'></audio></figure>"
                )
            rows.append("</div></div>")
        options = "".join(
            f"<label><input type=radio name={kind} value={v}{' checked' if v == current[kind] else ''}> {v} s</label> "
            for v in values
        )
        rows.append(
            f"<p class=pick>Pick: {options}<label><input type=radio name={kind} value=other> other: "
            f"<input type=number step=0.05 min=0 class=other data-kind={kind}></label></p></section>"
        )
    return TEMPLATE.replace("{rows}", "\n".join(rows)).replace(
        "{kinds}", json.dumps(list(found))
    )


TEMPLATE = """<!doctype html>
<html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1">
<title>Pause tuning</title>
<style>
:root { --bg: #fbfaf7; --text: #1d1d1b; --muted: #6b6a66; --line: #dddad2; --accent: #2f5d8a; }
@media (prefers-color-scheme: dark) { :root { --bg: #1b1c1e; --text: #ecebe7; --muted: #a3a19b; --line: #3a3b3e; --accent: #8db8e3; } }
body { background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px; }
h1 { margin-bottom: 0 } h2 { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 16px; }
.muted { color: var(--muted) } .example { margin: 12px 0 20px }
.row { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; }
figure { margin: 0; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px; }
figure.now { border-color: var(--accent) } figcaption { font-size: 14px; color: var(--muted) }
audio { width: 100% } .pick { background: color-mix(in srgb, var(--accent) 10%, transparent); padding: 8px 12px; border-radius: 8px; }
textarea { width: 100%; font: 14px ui-monospace, monospace; height: 9em; background: var(--bg); color: var(--text); border: 1px solid var(--line); }
input.other { width: 5em }
</style></head><body>
<h1>Pause tuning</h1>
<p class=muted>Real excerpts of the voiced sample passages, put together exactly as assembly does (each take trimmed, keeping 0.04 s at each end, then the pause). For each pause, listen to the examples at each length and pick one. The choices appear at the bottom: paste them back to Claude.</p>
<p class=muted><b>Setting and heard silence differ.</b> Each player shows the setting and the silence actually heard there (quieter than −50 dB). Between lines, the heard silence is the setting plus the 0.08 s kept at the two trimmed ends. Between sentences, inside one take, it is much longer: voicing joins the sentences as the voice model wrote them, each with its own silence at the end and start, which is not trimmed. If sentence pauses sound too long even at the shortest setting, that is the cause, and it can be fixed in voicing.</p>
{rows}
<h2>Your choices</h2>
<textarea id=out readonly></textarea>
<script>
const kinds = {kinds};
function update() {
  const picked = {};
  for (const k of kinds) {
    const r = document.querySelector(`input[name=${k}]:checked`);
    if (!r) continue;
    picked[k] = r.value === "other" ? Number(document.querySelector(`.other[data-kind=${k}]`).value) : Number(r.value);
  }
  document.getElementById("out").value = JSON.stringify(picked, null, 2);
}
document.addEventListener("input", update);
update();
</script></body></html>
"""


def main() -> None:
    current = pauses()
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    with get_sessionmaker()() as session:
        found = find_examples(session, current)
        for kind, examples in found.items():
            for n, ex in enumerate(examples):
                ex["heard"] = {}
                for v in VARIANTS[kind]:
                    audio, joins = render(ex, kind, v)
                    ex["heard"][v] = heard(audio, 24_000, joins)
                    soundfile.write(OUT / f"{kind}-{n + 1}-{v}.wav", audio, 24_000, subtype="PCM_16")
            print(kind, [f"{e['title']} ({e['voice']}): {e['text'][:60]}" for e in examples])
    (OUT / "listen.html").write_text(page(found, current), encoding="utf-8")


main()
