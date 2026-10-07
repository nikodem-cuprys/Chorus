"""PROTOTYPE, throwaway (ticket 24). Runs approach B (ticket 08) and the blind second labelling run (ticket 18) on
the six sample passages through one long-lived llama.cpp server in a Linux container, instead of one command-line
process per call. Logs every request to requests.jsonl and samples card memory to mem.csv.
The server must already be listening (see README.md). Run with any Python 3: python run.py [rounds]
Round 1 writes scripts/ and rerun/; later rounds repeat the same requests only to see whether the server hangs."""
import json, pathlib, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import llm  # noqa: E402
import approach_b  # noqa: E402

URL = "http://127.0.0.1:8080/completion"
TIMEOUT = 1200  # seconds; the longest call in ticket 08 took a few minutes, so this means "hung"
STAGE = {"round": 0, "passage": "", "pass": ""}
LOG = ROOT / "requests.jsonl"

SAMPLER = (
    "while ($true) { $n = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits).Trim(); "
    "$a = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | "
    "Sort-Object DedicatedUsage -Descending | Select-Object -First 1; "
    "'{0},{1},{2},{3}' -f [DateTimeOffset]::Now.ToUnixTimeSeconds(), $n, "
    "[math]::Round($a.DedicatedUsage/1MB), [math]::Round($a.SharedUsage/1MB); Start-Sleep -Seconds 2 }")


def chat(system, user, schema, max_tokens=4096):
    """Same prompt and settings as llm.chat, sent to the server."""
    prompt = (f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
              "<|im_start|>assistant\n<think>\n\n</think>\n\n")
    body = json.dumps({"prompt": prompt, "n_predict": max_tokens, "temperature": 0, "json_schema": schema}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    t = time.time()
    rec = dict(STAGE, n=llm.STATS["calls"] + 1, started=round(t, 1))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            res = json.loads(r.read())
    except Exception as e:  # a hang shows up here as a timeout
        rec.update(seconds=round(time.time() - t, 1), error=repr(e))
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        raise
    tm = res["timings"]
    rec.update(seconds=round(time.time() - t, 1), prompt_tokens=res["tokens_evaluated"], cached=tm.get("cache_n", 0),
               completion_tokens=tm["predicted_n"], tokens_per_second=round(tm["predicted_per_second"], 2),
               prompt_tokens_per_second=round(tm["prompt_per_second"], 1), truncated=res["truncated"],
               stop=res.get("stop_type"))
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    llm.STATS["calls"] += 1
    llm.STATS["seconds"] += time.time() - t
    llm.STATS["prompt_tokens"] += res["tokens_evaluated"]
    llm.STATS["completion_tokens"] += tm["predicted_n"]
    return json.loads(res["content"])


llm.chat = chat


def run(stem, keep):
    lines = json.loads((ATTR / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    STAGE.update(passage=stem)
    # first run, as approach_b.run: Character list, labels, Scenes (Scenes kept only so the timing matches ticket 08)
    t0, before = time.time(), dict(llm.STATS)
    parts = llm.chunks(lines)
    STAGE["pass"] = "cast"
    cast = approach_b.cast_pass(parts)
    STAGE["pass"] = "labels"
    labels = approach_b.attribution_pass(parts, cast)
    STAGE["pass"] = "scenes"
    scenes = llm.scenes(lines)
    first = {"passage": stem, "narrator": cast["narrator"], "characters": cast["characters"], "labels": labels,
             "scenes": scenes, "seconds": round(time.time() - t0, 1),
             "stats": {k: round(llm.STATS[k] - before[k], 1) for k in llm.STATS}}
    # second run, as review-queue/rerun.py: same Character list, 600-word chunks
    t1, before = time.time(), dict(llm.STATS)
    STAGE["pass"] = "second-run"
    again = approach_b.attribution_pass(llm.chunks(lines, max_words=600), cast)
    second = {"passage": stem, "labels": again, "seconds": round(time.time() - t1, 1),
              "stats": {k: round(llm.STATS[k] - before[k], 1) for k in llm.STATS}}
    if keep:
        for folder, out in (("scripts", first), ("rerun", second)):
            (ROOT / folder).mkdir(exist_ok=True)
            (ROOT / folder / f"{stem}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    differ = sorted(i for i in labels if again.get(i, {}).get("speaker") != labels[i]["speaker"])
    print(f"round {STAGE['round']} {stem} | first run {first['seconds']} s, {first['stats']['calls']} calls | "
          f"second run {second['seconds']} s, {second['stats']['calls']} calls | labelled {len(labels)} | "
          f"differ {len(differ)} | calls so far {llm.STATS['calls']}", flush=True)


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    with (ROOT / "mem.csv").open("a", encoding="utf-8") as mem:
        if mem.tell() == 0:
            mem.write("unix_time,nvidia_smi_used_mib,dedicated_mib,shared_mib\n")
            mem.flush()
        sampler = subprocess.Popen(["powershell", "-NoProfile", "-Command", SAMPLER], stdout=mem,
                                   stdin=subprocess.DEVNULL)
        try:
            for STAGE["round"] in range(1, rounds + 1):
                for stem in sorted(p.stem for p in (ATTR / "lines").glob("*.json")):
                    run(stem, keep=STAGE["round"] == 1)
            print("all done |", {k: round(v, 1) for k, v in llm.STATS.items()}, flush=True)
        finally:
            sampler.kill()
