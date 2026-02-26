#!/usr/bin/env bash
set -euo pipefail

# Bootstrap local model directories for course-step-extractor.
# Requires: huggingface-cli + prior `huggingface-cli login`.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${ROOT_DIR}/models"

mkdir -p "${MODELS_DIR}/reasoning" "${MODELS_DIR}/vlm" "${MODELS_DIR}/whisper"

echo "[1/3] Download reasoning model: Qwen/Qwen3.5-35B-A3B"
huggingface-cli download Qwen/Qwen3.5-35B-A3B \
  --local-dir "${MODELS_DIR}/reasoning/Qwen3.5-35B-A3B"

echo "[2/3] Download VLM model: google/gemma-3-27b-it"
huggingface-cli download google/gemma-3-27b-it \
  --local-dir "${MODELS_DIR}/vlm/gemma-3-27b-it"

echo "[3/3] Download ASR model: Systran/faster-whisper-large-v3"
huggingface-cli download Systran/faster-whisper-large-v3 \
  --local-dir "${MODELS_DIR}/whisper/faster-whisper-large-v3"

echo "Done. Models downloaded under: ${MODELS_DIR}"
