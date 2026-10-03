#!/bin/bash
# Launches the Cutroom MCP server over stdio, creating its virtualenv on first run.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  python3 -m venv "$DIR/.venv" >&2
  "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" >&2
fi
cd "$DIR"
exec "$DIR/.venv/bin/python" -m cutroom
