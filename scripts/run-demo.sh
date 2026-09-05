#!/bin/sh
set -eu

if ! python -c 'import ppiss, pygame, psutil' >/dev/null 2>&1; then
  echo "PPISS development environment is not active. Run 'direnv allow' or 'nix develop'." >&2
  exit 1
fi

PPISS_DEMO_SENDER_PID=
cleanup() {
  if [ -n "$PPISS_DEMO_SENDER_PID" ]; then
    kill "$PPISS_DEMO_SENDER_PID" 2>/dev/null || true
    wait "$PPISS_DEMO_SENDER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

python -m ppiss.sender --host 127.0.0.1 &
PPISS_DEMO_SENDER_PID=$!

python -m ppiss.display --windowed "$@"
