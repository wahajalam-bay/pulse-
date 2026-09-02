#!/usr/bin/env bash
# ZD PULSE — start on 127.0.0.1:4010. Works on Windows (Git Bash), macOS and Linux.
set -euo pipefail
DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
export MSYS_NO_PATHCONV=1          # Git Bash would rewrite /zd into a Windows path
export PORT="${PORT:-4010}" MOUNT="${MOUNT:-/zd}" HOST="${HOST:-127.0.0.1}"
exec python server.py
