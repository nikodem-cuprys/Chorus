# Small local language models and tools for speaker attribution and emotion reading within 4 GB

Type: research
Status: resolved
Blocked by: none

## Question

What is the best available way to do Speaker attribution (who says each line of dialogue, including untagged lines in back-and-forth exchanges), per-line Emotion tagging and per-Scene Mood tagging, running locally within 4 GB VRAM (quantized models via llama.cpp or Ollama, CPU offload allowed, slow is fine)? Cover: dedicated tools (e.g. BookNLP quote attribution, character clustering and coreference), published results on benchmarks such as PDNC, small LLMs that fit (e.g. 3-8B at Q4 with offload) and their reported accuracy on this task, hybrid approaches (rules + NER + an LLM for the hard cases), and how context-window limits affect a long novel. Note what carries over to non-English languages. Recommend 1-3 approaches for the prototype.

## Answer

- With a gold character list, attribution on PDNC is near-solved: ModernBERT joint scoring gets 94.5% (arXiv 2608.02359; repo has no license) and prompted Llama-3-8B gets 90.6% (NAACL 2025). Stock BookNLP (MIT, English only, runs on CPU) is weak on implicit and anaphoric quotes. In practice the hard part is finding the characters and merging their aliases.
- Qwen3.5-4B (Apache-2.0) at Q4_K_M is 2.74 GB, and with 16k context it fits fully in 4 GB. 8-9B models need CPU offload. Ollama supports the 1050 Ti (CC 6.1, driver 570 or newer).
- No reliable benchmark exists for Emotion or Mood in fiction, and scene segmentation is hard (F1 about 0.37). Treat both as reviewable LLM output that uses the TTS model's label set.
- Prototype: (A) BookNLP plus Qwen3.5-4B for hard quotes, character cleanup, Emotion and Mood; (B) LLM-only chunked attribution (4k chunks, global alias list), which is also the multilingual path; (C) optionally a go_emotions classifier as a baseline.
- Full findings: [research/analysis-models-in-4gb.md](../research/analysis-models-in-4gb.md). The coordinator writes this file, because the subagent was blocked from writing .md files.
