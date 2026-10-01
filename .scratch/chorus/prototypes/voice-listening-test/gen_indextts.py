"""PROTOTYPE, throwaway. IndexTTS-2 with the 8-float emotion vector from script.json.
Usage: python gen_indextts.py [fp16|fp32]   (fp16 stores weights in half precision to fit 4 GB)"""
import os, sys
import soundfile as sf
from harness import run, ROOT

mode = sys.argv[1] if len(sys.argv) > 1 else "fp16"
REPO = ROOT / "envs" / "index-tts"
CKPT = REPO / "checkpoints_2"


def load():
    os.chdir(REPO)  # IndexTTS resolves some assets relative to the repo
    from indextts.infer_v2 import IndexTTS2
    return IndexTTS2(cfg_path=str(CKPT / "config.yaml"), model_dir=str(CKPT),
                     use_fp16=(mode == "fp16"), use_cuda_kernel=False, use_deepspeed=False)


def synth(model, line, spk, emo):
    tmp = ROOT / "out" / f"indextts-2-{mode}" / f"_{line['id']}.tmp.wav"
    model.infer(spk_audio_prompt=str(ROOT / spk["ref"]), text=line["text"], output_path=str(tmp),
                emo_vector=emo["vector"], use_random=False, verbose=False)
    wav, sr = sf.read(tmp)
    tmp.unlink()
    return wav, sr


run(f"indextts-2-{mode}", load, synth, device_note=f"GPU, use_fp16={mode == 'fp16'}; emotion vector per Emotion")
