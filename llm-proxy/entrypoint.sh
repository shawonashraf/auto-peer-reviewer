#!/bin/sh
set -e
# LLM_API_FORMAT: auto (default) probes the endpoint; openai or anthropic skips the probe.
if [ "${LLM_API_FORMAT:=auto}" = "auto" ]; then
  LLM_API_FORMAT="$(python /app/detect_format.py)"
  echo "detected endpoint format: $LLM_API_FORMAT"
fi
case "$LLM_API_FORMAT" in
  openai) ;;
  anthropic)
    # LiteLLM appends /v1/messages itself, so drop a trailing /v1.
    LLM_BASE_URL="${LLM_BASE_URL%/}"; LLM_BASE_URL="${LLM_BASE_URL%/v1}"; export LLM_BASE_URL ;;
  *) echo "LLM_API_FORMAT must be auto, openai or anthropic, got '$LLM_API_FORMAT'" >&2; exit 1 ;;
esac
exec litellm --config "/app/${LLM_API_FORMAT}.yaml" --host 0.0.0.0 --port 4000
