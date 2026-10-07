"""PROTOTYPE, throwaway (ticket 25). Runs inside the container. Voices the eight lines of ticket 14 with Chatterbox 500M
and one of the memory settings:
  --half   weights stored in half precision on the card, turned into FP32 as each layer runs (compute stays FP32)
  --split  the two halves one at a time: T3 (text to speech tokens) for all lines, then S3Gen (tokens to audio)
  --cap N  refuse to hold more than N MiB on the card, as a card with no system-memory fallback (Linux) would
Each line uses the same seed for both halves, so settings can be compared take for take.
Usage: python fit.py <name> [--half] [--split] [--cap MIB] [--seed N]"""
import argparse, gc, json, pathlib, time, traceback

import librosa
import numpy as np
import perth
import soundfile as sf
import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from torch.nn.utils import parametrize

from chatterbox.models.s3gen import S3GEN_SR, S3Gen
from chatterbox.models.s3tokenizer import S3_SR, drop_invalid_tokens
from chatterbox.models.t3 import T3
from chatterbox.models.t3.modules.cond_enc import T3Cond
from chatterbox.models.tokenizers import EnTokenizer
from chatterbox.models.voice_encoder import VoiceEncoder
from chatterbox.tts import punc_norm

CKPT, VLT = pathlib.Path("/models/chatterbox"), pathlib.Path("/vlt")
SCRIPT = json.loads((VLT / "script.json").read_text(encoding="utf-8"))
MIB = 2**20


class ToFloat(torch.nn.Module):
    def forward(self, w):
        return w.float()


def halve(model):
    """Store every weight matrix in half precision; each use converts it to FP32 for that layer only."""
    stored = 0
    for m in list(model.modules()):
        if isinstance(m, parametrize.ParametrizationList):
            continue
        for name, p in list(m._parameters.items()):
            if p is not None and p.is_floating_point() and p.ndim >= 2:
                p.data = p.data.half()
                parametrize.register_parametrization(m, name, ToFloat(), unsafe=True)
                stored += p.numel() * 2
    # both models read their compute dtype from their first parameter, which is now half
    for cls in {type(x) for x in model.modules() if isinstance(getattr(type(x), "dtype", None), property)}:
        cls.dtype = property(lambda self: torch.float32)
    return round(stored / MIB)


def load(args):
    ve = VoiceEncoder()
    ve.load_state_dict(load_file(CKPT / "ve.safetensors"))
    t3 = T3()
    state = load_file(CKPT / "t3_cfg.safetensors")
    t3.load_state_dict(state["model"][0] if "model" in state else state)
    s3gen = S3Gen()
    s3gen.load_state_dict(load_file(CKPT / "s3gen.safetensors"), strict=False)
    half_mib = sum(halve(m) for m in (t3, s3gen)) if args.half else 0
    return ve.eval(), t3.eval(), s3gen.eval(), half_mib


def conditionals(ve, t3, s3gen, ref, exaggeration):
    """As ChatterboxTTS.prepare_conditionals; S3Gen's part runs wherever S3Gen is."""
    wav, _ = librosa.load(ref, sr=S3GEN_SR)
    wav16 = librosa.resample(wav, orig_sr=S3GEN_SR, target_sr=S3_SR)
    gen = s3gen.embed_ref(wav[:10 * S3GEN_SR], S3GEN_SR, device=s3gen.device)
    tokens, _ = s3gen.tokenizer.forward([wav16[:6 * S3_SR]], max_len=t3.hp.speech_cond_prompt_len)
    emb = torch.from_numpy(ve.embeds_from_wavs([wav16], sample_rate=S3_SR)).mean(axis=0, keepdim=True)
    cond = T3Cond(speaker_emb=emb, cond_prompt_speech_tokens=torch.atleast_2d(tokens),
                  emotion_adv=exaggeration * torch.ones(1, 1, 1)).to(device=t3.device)
    return cond, gen


def speech_tokens(t3, tokenizer, cond, text, cfg_weight, seed):
    tt = tokenizer.text_to_tokens(punc_norm(text)).to(t3.device)
    if cfg_weight > 0.0:
        tt = torch.cat([tt, tt], dim=0)
    tt = F.pad(F.pad(tt, (1, 0), value=t3.hp.start_text_token), (0, 1), value=t3.hp.stop_text_token)
    torch.manual_seed(seed)
    with torch.inference_mode():
        st = t3.inference(t3_cond=cond, text_tokens=tt, max_new_tokens=1000, cfg_weight=cfg_weight)[0]
    st = drop_invalid_tokens(st)
    return st[st < 6561]


def audio(s3gen, marker, tokens, gen, seed):
    gen = {k: v.to("cuda") if torch.is_tensor(v) else v for k, v in gen.items()}
    torch.manual_seed(seed)
    with torch.inference_mode():
        wav, _ = s3gen.inference(speech_tokens=tokens.to("cuda"), ref_dict=gen)
    return marker.apply_watermark(wav.squeeze(0).float().cpu().numpy(), sample_rate=S3GEN_SR)


def peak():
    return {"alloc_mib": round(torch.cuda.max_memory_allocated() / MIB),
            "reserved_mib": round(torch.cuda.max_memory_reserved() / MIB)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--cap", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()
    out = pathlib.Path("/out") / args.name
    out.mkdir(parents=True, exist_ok=True)
    total = torch.cuda.get_device_properties(0).total_memory
    if args.cap:
        torch.cuda.set_per_process_memory_fraction(min(1.0, args.cap * MIB / total))
    m = {"name": args.name, "half": args.half, "split": args.split, "cap_mib": args.cap, "seed": args.seed,
         "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0), "lines": []}
    recs = {l["id"]: {"id": l["id"]} for l in SCRIPT["lines"]}
    try:
        t0 = time.time()
        ve, t3, s3gen, m["half_stored_mib"] = load(args)
        tokenizer, marker = EnTokenizer(str(CKPT / "tokenizer.json")), perth.PerthImplicitWatermarker()
        ve.to("cuda")
        t3.to("cuda")
        if not args.split:
            s3gen.to("cuda")
        m["load_s"] = round(time.time() - t0, 1)
        m["after_load_mib"] = round(torch.cuda.memory_allocated() / MIB)
        todo = []
        for line in SCRIPT["lines"]:  # first half: text to speech tokens
            rec, emo = recs[line["id"]], SCRIPT["emotions"][line["emotion"]]
            t = time.time()
            cond, gen = conditionals(ve, t3, s3gen, VLT / SCRIPT["speakers"][line["speaker"]]["ref"], emo["exaggeration"])
            tokens = speech_tokens(t3, tokenizer, cond, line["text"], emo["cfg_weight"], args.seed)
            rec.update(t3_s=round(time.time() - t, 1), tokens=tokens.tolist())
            if args.split:
                todo.append((line, tokens.cpu(), {k: v.cpu() if torch.is_tensor(v) else v for k, v in gen.items()}))
            else:
                finish(s3gen, marker, line, tokens, gen, rec, out, args.seed)
        if args.split:  # swap: T3 leaves the card, S3Gen goes on
            m["t3_phase_peak"] = peak()
            t = time.time()
            del t3, ve, cond
            gc.collect()  # the half-precision wrappers form reference cycles; without this T3 stays on the card
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            s3gen.to("cuda")
            m["swap_s"] = round(time.time() - t, 1)
            for line, tokens, gen in todo:
                finish(s3gen, marker, line, tokens, gen, recs[line["id"]], out, args.seed)
            m["s3gen_phase_peak"] = peak()
        else:
            m["peak"] = peak()
    except Exception as e:
        m["error"] = f"{type(e).__name__}: {e}"[:600]
        m["peak_at_error"] = peak()
        traceback.print_exc()
    m["lines"] = list(recs.values())
    ok = [r for r in m["lines"] if "audio_s" in r]
    m["total_gen_s"] = round(sum(r["t3_s"] + r["s3gen_s"] for r in ok) + m.get("swap_s", 0), 1)
    m["total_audio_s"] = round(sum(r["audio_s"] for r in ok), 1)
    m["x_real_time"] = round(m["total_gen_s"] / m["total_audio_s"], 2) if ok else None
    (out / "metrics.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if k != "lines"}, indent=1), flush=True)


def finish(s3gen, marker, line, tokens, gen, rec, out, seed):
    t = time.time()
    wav = audio(s3gen, marker, tokens, gen, seed)
    sf.write(out / f"{line['id']}.wav", np.asarray(wav, dtype=np.float32), S3GEN_SR)
    rec.update(s3gen_s=round(time.time() - t, 1), audio_s=round(len(wav) / S3GEN_SR, 1))
    print(line["id"], {k: v for k, v in rec.items() if k != "tokens"}, flush=True)


if __name__ == "__main__":
    main()
