#!/usr/bin/env sh
# CodeMitra one-command setup for macOS and Linux (D-083); on Windows Git Bash it hands over to setup.ps1.
# Run it in the folder you cloned:   sh setup.sh
# It installs uv (Python tool manager) if missing, installs CodeMitra, then runs `codemitra setup`
# (Ollama, the model for this machine, the free Kaggle GPU, sharing). Safe to run again.
set -e
cd "$(dirname "$0")"

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*)
    exec powershell.exe -ExecutionPolicy Bypass -NoProfile -File setup.ps1 "$@" ;;
esac

echo "CodeMitra setup"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (Python tool manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"; export PATH
  command -v uv >/dev/null 2>&1 || { echo "uv did not install. Install it from https://docs.astral.sh/uv/ and run this again."; exit 1; }
fi

echo "Installing CodeMitra..."
uv tool install --reinstall -e . --python 3.12
uv tool update-shell >/dev/null 2>&1 || true

BIN="$(uv tool dir --bin)"
PATH="$BIN:$PATH"; export PATH
exec "$BIN/codemitra" setup "$@"
