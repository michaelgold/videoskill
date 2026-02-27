#!/usr/bin/env bash
set -euo pipefail

# Bootstrap local model directories for course-step-extractor.
# Requires: `hf` (new Hugging Face CLI) OR `huggingface-cli` (legacy),
# plus prior login (`hf auth login` or `huggingface-cli login`).

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${ROOT_DIR}/models"

if command -v huggingface-cli >/dev/null 2>&1; then
  HF_CMD=(huggingface-cli)
elif command -v hf >/dev/null 2>&1; then
  HF_CMD=(hf)
else
  echo "Error: neither 'huggingface-cli' nor 'hf' was found in PATH." >&2
  exit 1
fi

mkdir -p "${MODELS_DIR}/reasoning" "${MODELS_DIR}/vlm" "${MODELS_DIR}/whisper"

echo "Using HF CLI: ${HF_CMD[*]}"

echo "[1/3] Download reasoning model: Qwen/Qwen3.5-35B-A3B"
"${HF_CMD[@]}" download unsloth/Qwen3.5-35B-A3B-GGUF Qwen3.5-35B-A3B-Q4_K_M.gguf \
  --local-dir "${MODELS_DIR}/reasoning/Qwen3.5-35B-A3B"

echo "[2/3] Download VLM model: google/gemma-3-27b-it"
"${HF_CMD[@]}" download unsloth/gemma-3-27b-it-GGUF gemma-3-27b-it-Q4_K_M.gguf mmproj-F16.gguf \
  --local-dir "${MODELS_DIR}/vlm/gemma-3-27b-it"

echo "[3/3] Download ASR model: Systran/faster-whisper-large-v3"
"${HF_CMD[@]}" download Systran/faster-whisper-large-v3 \
  --local-dir "${MODELS_DIR}/whisper/faster-whisper-large-v3"

echo "Done. Models downloaded under: ${MODELS_DIR}"
