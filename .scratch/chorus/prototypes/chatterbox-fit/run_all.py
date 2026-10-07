"""PROTOTYPE, throwaway (ticket 25). Runs on Windows. Starts one container per memory setting (fit.py) and, from
outside, samples the card every two seconds: nvidia-smi's "used", and the Windows counters for memory on the card
(dedicated) and memory spilled into system memory (shared). Writes out/<name>/host_mem.json and out/summary.json.
Usage: python run_all.py [name ...]"""
import json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).parent
VLT = ROOT.parent / "voice-listening-test"
RUNS = {  # name -> fit.py flags; "capped" is filled in at run time with what is free on the card
    "no-change": [],
    "no-change-capped": ["--cap", "FREE"],
    "half": ["--half"],
    "split": ["--split"],
    "half-split": ["--half", "--split"],
}
SAMPLER = (
    "while ($true) { $n = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits).Trim(); "
    "$a = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | "
    "Sort-Object DedicatedUsage -Descending | Select-Object -First 1; "
    "'{0},{1},{2},{3}' -f [DateTimeOffset]::Now.ToUnixTimeSeconds(), $n, "
    "[math]::Round($a.DedicatedUsage/1MB), [math]::Round($a.SharedUsage/1MB); Start-Sleep -Seconds 2 }")
KEYS = ("nvidia_smi_used_mib", "dedicated_mib", "shared_mib")


def run(name):
    out = ROOT / "out" / name
    out.mkdir(parents=True, exist_ok=True)
    csv = out / "host_mem.csv"
    with csv.open("w", encoding="utf-8") as f:
        sampler = subprocess.Popen(["powershell", "-NoProfile", "-Command", SAMPLER], stdout=f, stdin=subprocess.DEVNULL)
        try:
            time.sleep(12)  # idle readings before the container starts
            rows = [list(map(int, l.split(","))) for l in csv.read_text(encoding="utf-8").split()]
            idle = dict(zip(KEYS, rows[-1][1:]))
            flags = [str(4096 - idle["dedicated_mib"]) if x == "FREE" else x for x in RUNS[name]]
            # TORCH_DISABLE_NATIVE_JIT: on Linux torch 2.14 sends some operations to triton kernels, which need a C
            # compiler at run time; off, torch takes the same path as on Windows (ticket 14)
            code = subprocess.run(["docker", "run", "--rm", "--gpus", "all", "-e", "TORCH_DISABLE_NATIVE_JIT=1",
                                   "-v", "chorus-models:/models:ro",
                                   "-v", f"{VLT}:/vlt:ro", "-v", f"{ROOT / 'out'}:/out", "-v", f"{ROOT}:/work:ro",
                                   "chorus-chatterbox-fit", "python", "/work/fit.py", name, *flags]).returncode
        finally:
            sampler.kill()
    rows = [list(map(int, l.split(","))) for l in csv.read_text(encoding="utf-8").split()]
    host = {"idle": idle, "peak": {k: max(r[i + 1] for r in rows) for i, k in enumerate(KEYS)}, "exit_code": code}
    (out / "host_mem.json").write_text(json.dumps(host, indent=1), encoding="utf-8")
    print(name, host, flush=True)


if __name__ == "__main__":
    for name in sys.argv[1:] or RUNS:
        run(name)
    summary = {}
    for name in RUNS:
        d = ROOT / "out" / name
        if (d / "metrics.json").exists() and (d / "host_mem.json").exists():
            m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
            summary[name] = {k: v for k, v in m.items() if k != "lines"} | {
                "host": json.loads((d / "host_mem.json").read_text(encoding="utf-8"))}
    (ROOT / "out" / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
