#!/usr/bin/env bash
set -euo pipefail

docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
  -e REG_ATLAS_NO_LLM="${REG_ATLAS_NO_LLM:-0}" \
  reg-atlas
