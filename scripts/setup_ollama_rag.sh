#!/usr/bin/env bash
#═══════════════════════════════════════════════════════════════════════════════
#  Asta — Install Ollama and pull the small RAG embedding model (nomic-embed-text)
#═══════════════════════════════════════════════════════════════════════════════
#
#  Usage:
#    ./scripts/setup_ollama_rag.sh        Pull nomic-embed-text (Ollama must be installed)
#    ./scripts/setup_ollama_rag.sh -i     Try to install Ollama first, then pull model
#
#  After this, start Ollama (if not already running):
#    ollama serve
#  Or open the Ollama app. Then Asta's Learning / RAG will use it.
#
#═══════════════════════════════════════════════════════════════════════════════

set -e
RAG_MODEL="nomic-embed-text"
OLLAMA_INSTALL_URL="https://ollama.com/install.sh"

install_ollama() {
  echo "Installing Ollama (may prompt for sudo)..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$OLLAMA_INSTALL_URL" | sh
  else
    echo "curl not found. Install Ollama manually: https://ollama.com/download"
    return 1
  fi
}

ensure_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    return 0
  fi
  echo "Ollama is not in your PATH."
  echo ""
  echo "Install it with (Linux):"
  echo "  curl -fsSL $OLLAMA_INSTALL_URL | sh"
  echo ""
  echo "Or download from: https://ollama.com/download"
  echo ""
  echo "Then run this script again to pull the RAG model."
  return 1
}

pull_model() {
  echo "Pulling RAG embedding model: $RAG_MODEL"
  ollama pull "$RAG_MODEL"
  echo ""
  echo "Done. Model $RAG_MODEL is ready for Asta's Learning / RAG."
  echo ""
  echo "If Ollama isn't running yet, start it with:"
  echo "  ollama serve"
  echo "Or open the Ollama app. Default URL: http://localhost:11434"
}

TRY_INSTALL=false
while getopts "i" o; do
  case "$o" in
    i) TRY_INSTALL=true ;;
    *) echo "Usage: $0 [-i]" ; echo "  -i  Install Ollama first (Linux: curl | sh)" ; exit 1 ;;
  esac
done

if "$TRY_INSTALL"; then
  install_ollama || exit 1
fi

ensure_ollama || exit 1
pull_model
