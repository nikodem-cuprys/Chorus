"""PROTOTYPE, throwaway. Shared runner for the voice listening test.

Each model script calls run(name, load, synth). load() returns a model;
synth(model, line, speaker, emotion) returns (numpy float waveform, sample_rate).
Writes out/<name>/<line id>.wav and out/<name>/metrics.json.
"""
import json, os, pathlib, subprocess, sys, time, threading, traceback

import numpy as np
import soundfile as sf
import torch

ROOT = pathlib.Path(__file__).parent
SCRIPT = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))


def smi_used():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=5).stdout
    return int(out.strip().splitlines()[0])


class SmiPeak:
    """Poll nvidia-smi for whole-card memory use (includes the desktop's share)."""

    def __init__(self):
        self.idle = self.peak = 0
        self._stop = False
        self.t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop:
            try:
                self.peak = max(self.peak, smi_used())
            except Exception:
                pass
            time.sleep(0.5)

    def __enter__(self):
        self.idle = self.peak = smi_used()  # read once before the thread starts, so idle is never 0
        self.t.start()
        return self

    def __exit__(self, *a):
        self._stop = True


WIN_COUNTERS = r"""
$p = '\GPU Process Memory(pid_%d_*)\Dedicated Usage', '\GPU Process Memory(pid_%d_*)\Shared Usage'
$a = '\GPU Adapter Memory(*)\Dedicated Usage', '\GPU Adapter Memory(*)\Shared Usage'
while ($true) {
  foreach ($c in @($a, $p)) {
    $s = Get-Counter -Counter $c -ErrorAction SilentlyContinue
    if ($s) { $s.CounterSamples | ForEach-Object { '{0}|{1}' -f $_.Path, $_.CookedValue } }
  }
  '---'
}
"""


class WinGpuMem:
    """Windows GPU counters: dedicated (on the card) and shared (spilled into system memory) use,
    for the whole adapter and for this process alone. nvidia-smi cannot see the shared part."""

    KEYS = ("adapter_dedicated", "adapter_shared", "process_dedicated", "process_shared")

    def __init__(self):
        self.idle, self.peak, self.proc = {}, dict.fromkeys(self.KEYS, 0), None

    def _run(self):
        cur = dict.fromkeys(self.KEYS, 0)
        for raw in self.proc.stdout:
            raw = raw.strip().lower()
            if raw == "---":
                if not self.idle:
                    self.idle = dict(cur)
                for k in self.KEYS:
                    self.peak[k] = max(self.peak[k], cur[k])
                cur = dict.fromkeys(self.KEYS, 0)
                continue
            path, _, val = raw.rpartition("|")
            try:
                mib = round(float(val.replace(",", ".")) / 2**20)
            except ValueError:
                continue
            kind = "dedicated" if path.endswith("dedicated usage") else "shared"
            if "gpu process memory" in path:
                cur[f"process_{kind}"] += mib  # one instance per adapter the process touches
            elif "gpu adapter memory" in path:
                cur[f"adapter_{kind}"] = max(cur[f"adapter_{kind}"], mib)  # the busiest adapter is the 1050 Ti

    def __enter__(self):
        if os.name != "nt":
            return self
        pid = os.getpid()
        self.proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", WIN_COUNTERS % (pid, pid)],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        threading.Thread(target=self._run, daemon=True).start()
        for _ in range(60):  # wait for the first sample so there is an idle reading
            if self.idle:
                break
            time.sleep(0.5)
        return self

    def __exit__(self, *a):
        if self.proc:
            self.proc.kill()


def run(name, load, synth, device_note=""):
    out = ROOT / "out" / name
    out.mkdir(parents=True, exist_ok=True)
    cuda = torch.cuda.is_available()
    metrics = {"model": name, "device_note": device_note, "torch": torch.__version__,
               "gpu": torch.cuda.get_device_name(0) if cuda else None, "lines": []}
    with SmiPeak() as smi, WinGpuMem() as win:
        t0 = time.time()
        model = load()
        metrics["load_s"] = round(time.time() - t0, 1)
        if cuda:
            metrics["vram_after_load_mib"] = round(torch.cuda.memory_allocated() / 2**20)
            torch.cuda.reset_peak_memory_stats()
        for line in SCRIPT["lines"]:
            spk = SCRIPT["speakers"][line["speaker"]]
            emo = SCRIPT["emotions"][line["emotion"]]
            rec = {"id": line["id"], "speaker": line["speaker"], "emotion": line["emotion"]}
            try:
                t = time.time()
                wav, sr = synth(model, line, spk, emo)
                gen = time.time() - t
                wav = np.asarray(wav, dtype=np.float32).squeeze()
                sf.write(out / f"{line['id']}.wav", wav, sr)
                dur = len(wav) / sr
                rec.update(gen_s=round(gen, 1), audio_s=round(dur, 1), rtf=round(gen / dur, 2) if dur else None)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            print(name, rec, flush=True)
            metrics["lines"].append(rec)
        if cuda:
            metrics["torch_peak_alloc_mib"] = round(torch.cuda.max_memory_allocated() / 2**20)
            metrics["torch_peak_reserved_mib"] = round(torch.cuda.max_memory_reserved() / 2**20)
        metrics["card_idle_mib_at_start"] = smi.idle
        metrics["card_peak_mib"] = smi.peak
        if win.proc:
            time.sleep(3)  # let the counter loop take a last sample
            metrics["win_idle_mib"] = win.idle
            metrics["win_peak_mib"] = win.peak
    ok = [l for l in metrics["lines"] if "rtf" in l and l["rtf"]]
    metrics["total_gen_s"] = round(sum(l["gen_s"] for l in ok), 1)
    metrics["total_audio_s"] = round(sum(l["audio_s"] for l in ok), 1)
    metrics["mean_rtf"] = round(metrics["total_gen_s"] / metrics["total_audio_s"], 2) if ok else None
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in metrics.items() if k != "lines"}, indent=2))


if __name__ == "__main__":
    sys.exit("import this from a model script")
