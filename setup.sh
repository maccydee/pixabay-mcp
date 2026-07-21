#!/usr/bin/env bash
# One-command setup for macOS / Linux: isolated venv + MCP SDK, then prints the
# exact Claude Desktop config block with your real absolute paths.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

PYTHON="${PYTHON:-python3}"

echo "→ Creating virtual environment (.venv) …"
"$PYTHON" -m venv .venv

echo "→ Installing the MCP SDK …"
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet "mcp>=1.2.0"

echo "→ Verifying the server imports …"
./.venv/bin/python -c "import pixabay.server" && echo "  ok."

cat <<EOF

──────────────────────────────────────────────────────────────────────────────
Setup complete. Paste this into your Claude Desktop config:

  macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
  Linux:   ~/.config/Claude/claude_desktop_config.json

If the file already has an "mcpServers" object, add only the "pixabay" entry.
──────────────────────────────────────────────────────────────────────────────

{
  "mcpServers": {
    "pixabay": {
      "command": "$here/.venv/bin/python",
      "args": ["$here/run_server.py"],
      "env": { "PIXABAY_API_KEY": "your-key-here" }
    }
  }
}

Then fully quit and reopen Claude Desktop. Get a free key at
https://pixabay.com/api/docs/ (a demo key is used if you leave the placeholder).
EOF
