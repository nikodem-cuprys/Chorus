#!/usr/bin/env bash
# PROTOTYPE, throwaway. Run every candidate one at a time, then rebuild listen.html.
# Safe to re-run: models whose metrics.json already exists are skipped.
set -u
ROOT="/d/projcets/Chorus/.scratch/chorus/prototypes/voice-listening-test"
WIN_ROOT='D:\projcets\Chorus\.scratch\chorus\prototypes\voice-listening-test'
export HF_HOME="$WIN_ROOT\\hf-cache" HF_HUB_DOWNLOAD_TIMEOUT=120 PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
LOG="$ROOT/run.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
page() { "$ROOT/envs/kokoro/Scripts/python.exe" "$ROOT/build_page.py" >>"$LOG" 2>&1; }

gen() {  # out-dir name, env, script, args...
  local name="$1" env="$2"; shift 2
  if [ -f "$ROOT/out/$name/metrics.json" ]; then log "skip $name (done)"; return; fi
  log "run $name"
  (cd "$ROOT" && "$ROOT/envs/$env/Scripts/python.exe" "$@") >>"$LOG" 2>&1 && log "done $name" || log "FAILED $name"
  page
}

gen chatterbox-500m chatterbox gen_chatterbox.py 500m
gen chatterbox-turbo chatterbox gen_chatterbox.py turbo
gen qwen3-tts-0.6b qwen gen_qwen.py

if [ ! -f "$ROOT/envs/index-tts/checkpoints_2/config.yaml" ] || [ ! -f "$ROOT/envs/index-tts/checkpoints_2/gpt.pth" ] || [ -n "$(find "$ROOT/envs/index-tts/checkpoints_2" -name '*.incomplete' 2>/dev/null)" ]; then
  log "downloading IndexTTS-2 checkpoints"
  for i in $(seq 1 20); do
    "$ROOT/envs/tools/Scripts/hf.exe" download IndexTeam/IndexTTS-2 --local-dir "$WIN_ROOT\\envs\\index-tts\\checkpoints_2" >>"$LOG" 2>&1 && break
    log "retry checkpoint download ($i)"; sleep 20
  done
fi
gen indextts-2-fp16 index-tts-env gen_indextts.py fp16
page
log "all done"
