"""PROTOTYPE, throwaway. Runs Qwen3.5-4B (Q4_K_M) through llama.cpp's command-line program with JSON-schema output,
plus the Mood-per-Scene prompt shared by the approaches. One process per call: the llama.cpp server (build b11318)
hung after one or two requests on this machine; the command-line program does not."""
import json, pathlib, re, subprocess, tempfile, time

LLM_DIR = pathlib.Path(r"C:\Users\nikod\AppData\Local\chorus-frozen\llm")
EXE, MODEL = LLM_DIR / "llama" / "llama-completion.exe", LLM_DIR / "Qwen3.5-4B-Q4_K_M.gguf"
EMOTIONS = ["neutral", "happy", "excited", "amused", "angry", "sad", "afraid", "surprised", "disgusted", "anxious"]
MOODS = ["calm", "cheerful", "comic", "tense", "ominous", "melancholic", "angry", "anxious"]
STATS = {"calls": 0, "seconds": 0.0, "prompt_tokens": 0, "completion_tokens": 0}


def chat(system, user, schema, max_tokens=4096):
    # ChatML with an empty think block: Qwen answers directly, without reasoning first
    prompt = (f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
              "<|im_start|>assistant\n<think>\n\n</think>\n\n")
    with tempfile.TemporaryDirectory() as d:
        pf, sf = pathlib.Path(d) / "p.txt", pathlib.Path(d) / "s.json"
        pf.write_text(prompt, encoding="utf-8", newline="\n")
        sf.write_text(json.dumps(schema), encoding="utf-8")
        t = time.time()
        r = subprocess.run([str(EXE), "-m", str(MODEL), "-ngl", "all", "-c", "8192", "-f", str(pf), "-jf", str(sf),
                            "-n", str(max_tokens), "--temp", "0", "-no-cnv", "--no-display-prompt", "--no-warmup"],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=3600)
    out, err = r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    STATS["calls"] += 1
    STATS["seconds"] += time.time() - t
    for key, pat in (("prompt_tokens", r"prompt eval time.*?/\s*(\d+) tokens"),
                     ("completion_tokens", r"\beval time.*?/\s*(\d+) runs")):
        m = re.search(pat, err)
        STATS[key] += int(m[1]) if m else 0
    return json.loads(out.replace("[end of text]", "").strip())


def chunks(lines, max_words=900):
    """Group whole paragraphs into chunks of about max_words, as a long Work would be processed."""
    out, cur, words = [], [], 0
    paras = {}
    for l in lines:
        paras.setdefault(l["para"], []).append(l)
    for p in sorted(paras):
        n = sum(len(l["text"].split()) for l in paras[p])
        if cur and words + n > max_words:
            out.append(cur)
            cur, words = [], 0
        cur.extend(paras[p])
        words += n
    if cur:
        out.append(cur)
    return out


def render(lines, mark_quotes=True, anchors=None):
    """Chunk text with each quote prefixed by its id, e.g. [12] “...”; paragraphs on separate lines.
    anchors maps a quote id to a Speaker that is already known: [12 = Alice] “...”."""
    out, para = [], None
    for l in lines:
        if l["para"] != para:
            out.append("\n\n")
            para = l["para"]
        tag = ""
        if mark_quotes and l["kind"] == "quote":
            known = (anchors or {}).get(l["id"])
            tag = f"[{l['id']} = {known}] " if known else f"[{l['id']}] "
        out.append(tag + l["text"] + " ")
    return "".join(out).strip()


def scenes(lines):
    """Mood per Scene over the whole passage (coarse by design)."""
    text = "".join(f"\n\n(paragraph {p}) " + " ".join(l["text"] for l in lines if l["para"] == p)
                   for p in sorted({l["para"] for l in lines}))
    schema = {"type": "object", "required": ["scenes"], "additionalProperties": False, "properties": {"scenes": {
        "type": "array", "maxItems": 5, "items": {"type": "object", "additionalProperties": False,
                                   "required": ["first_paragraph", "setting", "mood"],
                                   "properties": {"first_paragraph": {"type": "integer"}, "setting": {"type": "string"},
                                                  "mood": {"type": "string", "enum": MOODS}}}}}}
    res = chat("You split a passage of fiction into Scenes. A Scene is a continuous stretch with one setting and one "
               "mood. Use as few Scenes as possible; most passages have one to three. For each Scene give the number of "
               "its first paragraph, a setting of a few words, and its mood.", text.strip(), schema, max_tokens=600)
    return res["scenes"]
