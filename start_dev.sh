#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_LOCAL="compose/.env.local"
ENV_TEMPLATE="compose/.env.example.insecure"
LLM_API_KEY_VALUE=""
LLM_CHAT_MODEL_VALUE=""
RESET_ENV=0

usage() {
  cat <<'USAGE'
Usage: ./start_dev.sh [options]

Options:
  --llm-api-key <value>     Set ARP_LLM_API_KEY in compose/.env.local
  --llm-chat-model <value>  Set ARP_LLM_CHAT_MODEL in compose/.env.local
  --env-local <path>        Path to env file (default: compose/.env.local)
  --template <path>         Template to copy from (default: compose/.env.example.insecure)
  --reset-env               Overwrite env file from template
  -h, --help                Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --llm-api-key)
      LLM_API_KEY_VALUE="${2:-}"
      shift 2
      ;;
    --llm-chat-model)
      LLM_CHAT_MODEL_VALUE="${2:-}"
      shift 2
      ;;
    --env-local)
      ENV_LOCAL="${2:-}"
      shift 2
      ;;
    --template)
      ENV_TEMPLATE="${2:-}"
      shift 2
      ;;
    --reset-env)
      RESET_ENV=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$RESET_ENV" -eq 1 || ! -f "$ENV_LOCAL" ]]; then
  if [[ ! -f "$ENV_TEMPLATE" ]]; then
    echo "Missing template: $ENV_TEMPLATE"
    exit 1
  fi
  cp "$ENV_TEMPLATE" "$ENV_LOCAL"
  echo "Wrote $ENV_LOCAL from $ENV_TEMPLATE"
fi

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  python3 - "$key" "$value" "$file" <<'PY'
import sys
from pathlib import Path

key, value, file_path = sys.argv[1], sys.argv[2], sys.argv[3]
path = Path(file_path)
lines = []
found = False
if path.exists():
    lines = path.read_text(encoding="utf-8").splitlines()
for idx, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[idx] = f"{key}={value}"
        found = True
        break
if not found:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

if [[ -n "$LLM_API_KEY_VALUE" ]]; then
  set_env_value "ARP_LLM_API_KEY" "$LLM_API_KEY_VALUE" "$ENV_LOCAL"
fi

if [[ -n "$LLM_CHAT_MODEL_VALUE" ]]; then
  set_env_value "ARP_LLM_CHAT_MODEL" "$LLM_CHAT_MODEL_VALUE" "$ENV_LOCAL"
fi

missing=0
for key in ARP_LLM_API_KEY ARP_LLM_CHAT_MODEL; do
  value="$(grep -E "^${key}=" "$ENV_LOCAL" | tail -n1 | cut -d= -f2- | xargs)"
  if [[ -z "$value" ]]; then
    echo "Missing ${key} in $ENV_LOCAL"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "Set the missing values in $ENV_LOCAL or pass --llm-api-key/--llm-chat-model."
  exit 1
fi

STACK_VERSION="$(grep -E '^STACK_VERSION=' "$ENV_LOCAL" | tail -n1 | cut -d= -f2- | xargs)"
if [[ -z "$STACK_VERSION" ]]; then
  echo "STACK_VERSION is not set in $ENV_LOCAL"
  exit 1
fi

python3 -m pip install -e .
arp-jarvis versions

arp-jarvis stack pull
arp-jarvis stack up -d

echo "Waiting for stack to be ready..."
ready=0
for ((i=1; i<=30; i++)); do
  if arp-jarvis --json doctor >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "$ready" -eq 1 ]]; then
  arp-jarvis doctor
else
  echo "Stack did not become ready in time."
  arp-jarvis doctor || true
  exit 1
fi

echo "Done. Stack is running in dev-insecure mode."
