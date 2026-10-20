"""The voice model behind an interface (docs/spec/02-architecture.md, Engines), with its one
implementation: Chatterbox 500M (`chatterbox-tts==0.1.7`).

Chatterbox is loaded from the models volume with `ChatterboxTTS.from_local`, onto the CPU, and its
two halves take turns on the card (GPU turn-taking): for a batch of speech, T3 (text to speech
tokens) goes onto the card and runs over the whole batch, goes back off, then S3Gen (speech tokens
to audio) goes on and runs over the same batch. Compute is FP32. Each piece of speech is seeded
before each half, so the same seed gives the same take. The watermark stays on.

Torch and Chatterbox are imported only when the model is opened: the web service and the unit
tests never load them.
"""

import gc
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

SAMPLE_RATE = 24_000
# What ChatterboxTTS.generate samples with; every listening test used these.
SAMPLING = {"temperature": 0.8, "repetition_penalty": 1.2, "min_p": 0.05, "top_p": 1.0}


@dataclass(frozen=True)
class Speech:
    """One piece of text to speak: a sentence of a line."""

    text: str
    # The Voice's reference clip.
    reference: Path
    exaggeration: float
    cfg_weight: float
    seed: int


class VoiceModel(Protocol):
    sample_rate: int

    def speak(self, batch: list[Speech]) -> Iterator[tuple[Speech, np.ndarray]]:
        """Each piece of the batch with its audio (mono float32 at `sample_rate`), in order."""
        ...


class Chatterbox:
    """Use as a context manager: the model is loaded on entry and freed on exit."""

    sample_rate = SAMPLE_RATE

    def __init__(self, folder: Path, device: str = "cuda"):
        self.folder = folder
        self.device = device
        self._references: dict[Path, tuple] = {}

    def __enter__(self) -> "Chatterbox":
        # S3Gen's buffers grow with the length of what it says; with the default allocator a
        # 35 s sentence left 3.85 GB reserved on the card for 2.4 GB in use. Growable segments
        # keep the reserve near what is used (2.37 GB). Read when CUDA first allocates.
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        from chatterbox.tts import ChatterboxTTS

        # Everything starts on the CPU; the halves visit the card in turn.
        self.tts = ChatterboxTTS.from_local(self.folder, "cpu")
        return self

    def __exit__(self, *_: object) -> None:
        import torch

        self.tts = None
        self._references.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _reference(self, path: Path) -> tuple:
        """The speaker embedding, prompt tokens and S3Gen reference of a clip, on the CPU; as
        ChatterboxTTS.prepare_conditionals, once per clip."""
        if path not in self._references:
            self.tts.prepare_conditionals(str(path))
            conds = self.tts.conds
            self._references[path] = (
                conds.t3.speaker_emb,
                conds.t3.cond_prompt_speech_tokens,
                conds.gen,
            )
        return self._references[path]

    def speak(self, batch: list[Speech]) -> Iterator[tuple[Speech, np.ndarray]]:
        import torch
        import torch.nn.functional as F
        from chatterbox.models.s3tokenizer import drop_invalid_tokens
        from chatterbox.models.t3.modules.cond_enc import T3Cond
        from chatterbox.tts import punc_norm

        tts = self.tts
        for speech in batch:
            self._reference(speech.reference)

        # T3 over the whole batch.
        tts.t3.to(self.device)
        tokens = []
        try:
            for speech in batch:
                embedding, prompt, _ = self._references[speech.reference]
                cond = T3Cond(
                    speaker_emb=embedding,
                    cond_prompt_speech_tokens=prompt,
                    emotion_adv=speech.exaggeration * torch.ones(1, 1, 1),
                ).to(device=self.device)
                text = tts.tokenizer.text_to_tokens(punc_norm(speech.text)).to(self.device)
                if speech.cfg_weight > 0.0:
                    text = torch.cat([text, text], dim=0)  # two sequences for CFG
                text = F.pad(text, (1, 0), value=tts.t3.hp.start_text_token)
                text = F.pad(text, (0, 1), value=tts.t3.hp.stop_text_token)
                torch.manual_seed(speech.seed)
                with torch.inference_mode():
                    out = tts.t3.inference(
                        t3_cond=cond,
                        text_tokens=text,
                        max_new_tokens=1000,
                        cfg_weight=speech.cfg_weight,
                        **SAMPLING,
                    )[0]
                out = drop_invalid_tokens(out)
                tokens.append(out[out < 6561].cpu())
        finally:
            tts.t3.to("cpu")
            torch.cuda.empty_cache()

        # S3Gen over the same batch.
        tts.s3gen.to(self.device)
        try:
            for speech, speech_tokens in zip(batch, tokens, strict=True):
                gen = {
                    k: v.to(self.device) if torch.is_tensor(v) else v
                    for k, v in self._references[speech.reference][2].items()
                }
                torch.manual_seed(speech.seed)
                with torch.inference_mode():
                    wav, _ = tts.s3gen.inference(
                        speech_tokens=speech_tokens.to(self.device), ref_dict=gen
                    )
                wav = wav.squeeze(0).float().cpu().numpy()
                marked = tts.watermarker.apply_watermark(wav, sample_rate=SAMPLE_RATE)
                yield speech, np.asarray(marked, dtype=np.float32)
        finally:
            tts.s3gen.to("cpu")
            torch.cuda.empty_cache()
