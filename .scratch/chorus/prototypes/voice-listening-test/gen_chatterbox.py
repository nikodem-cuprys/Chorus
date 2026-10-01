"""PROTOTYPE, throwaway. Chatterbox 500M (exaggeration dial) or Chatterbox-Turbo 350M (no emotion dial).
Usage: python gen_chatterbox.py 500m|turbo [out-dir suffix]"""
import sys
from harness import run, ROOT

variant = sys.argv[1] if len(sys.argv) > 1 else "500m"
suffix = sys.argv[2] if len(sys.argv) > 2 else ""


def load():
    if variant == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        return ChatterboxTurboTTS.from_pretrained(device="cuda")
    from chatterbox.tts import ChatterboxTTS
    return ChatterboxTTS.from_pretrained(device="cuda")


def synth(model, line, spk, emo):
    kw = {"audio_prompt_path": str(ROOT / spk["ref"])}
    if variant != "turbo":  # Turbo ignores these
        kw.update(exaggeration=emo["exaggeration"], cfg_weight=emo["cfg_weight"])
    wav = model.generate(line["text"], **kw)
    return wav.cpu().numpy(), model.sr


run(f"chatterbox-{variant}{suffix}", load, synth,
    device_note="GPU fp32" + ("; exaggeration/cfg per Emotion" if variant != "turbo" else "; no emotion control"))
