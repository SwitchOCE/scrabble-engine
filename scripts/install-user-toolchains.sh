#!/usr/bin/env bash
# Install Go and Rust into the user's home directory (no sudo).
set -euo pipefail
GO_VERSION="${GO_VERSION:-$(curl -fsSL 'https://go.dev/VERSION?m=text' | head -1)}"

if ! command -v go >/dev/null && [ ! -x "$HOME/.local/go/bin/go" ]; then
  echo "Installing $GO_VERSION to ~/.local/go"
  mkdir -p "$HOME/.local"
  curl -fsSL "https://go.dev/dl/${GO_VERSION}.linux-amd64.tar.gz" | tar -C "$HOME/.local" -xz
fi

if ! command -v cargo >/dev/null && [ ! -x "$HOME/.cargo/bin/cargo" ]; then
  echo "Installing Rust (rustup, stable)"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
fi

cat <<'MSG'
Done. Add to your shell profile if not already there:
  export PATH="$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$PATH"
MSG
