#!/usr/bin/env bash
# PROTOTYPE, throwaway. Sequential, resumable setup of the three GPU environments,
# all sharing ONE locally downloaded torch 2.8.0+cu126 (Pascal sm_61 kernels included).
# Safe to re-run: finished steps are skipped.
set -u
ROOT="/d/projcets/Chorus/.scratch/chorus/prototypes/voice-listening-test"
WIN_ROOT='D:\projcets\Chorus\.scratch\chorus\prototypes\voice-listening-test'
PY311='C:\Users\nikod\AppData\Local\Programs\Python\Python311\python.exe'
UV="$ROOT/envs/tools/Scripts/uv.exe"
export UV_CACHE_DIR="$WIN_ROOT\\uv-cache" UV_LINK_MODE=copy UV_HTTP_TIMEOUT=600
LOG="$ROOT/setup.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

mkdir -p "$ROOT/wheels"
fetch() {  # resumable download with retries
  local url="$1" out="$ROOT/wheels/$2" size="$3"
  for i in $(seq 1 30); do
    [ -f "$out" ] && [ "$(stat -c %s "$out")" = "$size" ] && { log "have $2"; return 0; }
    log "downloading $2 (attempt $i, $( [ -f "$out" ] && stat -c %s "$out" || echo 0 ) of $size bytes)"
    curl -sS -L -C - --retry 5 --retry-delay 10 -o "$out" "$url"
    sleep 5
  done
  log "FAILED to download $2"; return 1
}
TORCH=torch-2.8.0+cu126-cp311-cp311-win_amd64.whl
AUDIO=torchaudio-2.8.0+cu126-cp311-cp311-win_amd64.whl
fetch "https://download.pytorch.org/whl/cu126/torch-2.8.0%2Bcu126-cp311-cp311-win_amd64.whl" "$TORCH" \
  "$(curl -sIL "https://download.pytorch.org/whl/cu126/torch-2.8.0%2Bcu126-cp311-cp311-win_amd64.whl" | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')" || exit 1
fetch "https://download.pytorch.org/whl/cu126/torchaudio-2.8.0%2Bcu126-cp311-cp311-win_amd64.whl" "$AUDIO" \
  "$(curl -sIL "https://download.pytorch.org/whl/cu126/torchaudio-2.8.0%2Bcu126-cp311-cp311-win_amd64.whl" | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')" || exit 1

printf 'torch==2.8.0+cu126\ntorchaudio==2.8.0+cu126\n' > "$ROOT/overrides.txt"
check() {  # env name -> prints torch info or fails
  "$ROOT/envs/$1/Scripts/python.exe" -c "import torch; assert torch.cuda.is_available(); print('$1', torch.__version__, torch.cuda.get_arch_list())" 2>&1 | tail -1 | tee -a "$LOG"
  "$ROOT/envs/$1/Scripts/python.exe" -c "import torch; assert 'sm_61' in torch.cuda.get_arch_list()" 2>/dev/null
}
mkenv() {  # name, then install args
  local name="$1"; shift
  if check "$name" >/dev/null 2>&1; then log "env $name already OK"; return 0; fi
  log "creating env $name"
  "$UV" venv --python "$PY311" "$WIN_ROOT\\envs\\$name" >>"$LOG" 2>&1
  "$UV" pip install --python "$WIN_ROOT\\envs\\$name\\Scripts\\python.exe" \
      --find-links "$WIN_ROOT\\wheels" --override "$WIN_ROOT\\overrides.txt" --index-strategy unsafe-best-match \
      "$@" >>"$LOG" 2>&1 || { log "install FAILED for $name (see log)"; return 1; }
  check "$name" && log "env $name OK" || log "env $name torch check FAILED"
}

mkenv chatterbox torch torchaudio chatterbox-tts soundfile
mkenv qwen torch torchaudio qwen-tts soundfile
mkenv index-tts-env torch torchaudio soundfile --no-sources -e "$WIN_ROOT\\envs\\index-tts"
log "setup finished"
