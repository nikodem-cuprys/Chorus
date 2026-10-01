"""PROTOTYPE, throwaway. Qwen3-TTS 0.6B-Base: cloning only, Emotion comes from the text itself.
Pascal: no flash-attention, no bf16 compute, so load as fp32 with SDPA."""
import torch
from harness import run, ROOT

MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


def load():
    from qwen_tts import Qwen3TTSModel
    return Qwen3TTSModel.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.float32, attn_implementation="sdpa")


def synth(model, line, spk, emo):
    ref = ROOT / spk["ref"]
    txt = ref.with_suffix(".txt")
    kw = {"ref_text": txt.read_text(encoding="utf-8")} if txt.exists() else {"x_vector_only_mode": True}
    wavs, sr = model.generate_voice_clone(text=line["text"], language="English", ref_audio=str(ref), **kw)
    return wavs[0], sr


run("qwen3-tts-0.6b", load, synth, device_note="GPU fp32, SDPA; no emotion control (text only); narrator cloned in x-vector-only mode")
