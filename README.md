# Pixabay MCP

A token-lean [MCP](https://modelcontextprotocol.io) server for the Pixabay
image & video API. Search returns compact results; a 24-hour disk cache makes
pagination and detail lookups nearly free; downloads are stored server-side so
you never hotlink.

## Why it's cheap on tokens

Raw Pixabay responses are large (a 100-hit page is ~33k tokens). This server:

- returns only ~12 **slim** hits per call (id, tags, dimensions, a couple of
  URLs, contributor) instead of the ~25-field raw records;
- trims tags to 8 by default (`full_tags=true` to keep all);
- caches the full response to disk and serves further pages from a `result_id`
  handle — paging and detail lookups usually cost **zero** API requests and only
  the tokens of the 12 hits shown.

## Pixabay terms baked in

- **24h caching** of responses (required by Pixabay) — handled automatically.
- **Attribution** — every search result and download carries an attribution
  string / `attribution_notice`. Display it wherever results are shown.
- **No hotlinking** of images — `download_asset` saves to your server first.
- **Rate limit** (100 req / 60s) — client reads the limit headers and backs off
  on 429.

## Use it in Claude Desktop

**1. Run the setup script** (creates an isolated venv, installs the MCP SDK, and
prints the exact config with your real absolute paths):

macOS / Linux:
```bash
cd pixabay-mcp
bash setup.sh
```

Windows (PowerShell):
```powershell
cd pixabay-mcp
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**2. Paste the printed block** into your Claude Desktop config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

If the file already has an `mcpServers` object, add only the `"pixabay"` entry
inside it. The block looks like:

```json
{
  "mcpServers": {
    "pixabay": {
      "command": "/abs/path/.venv/bin/python",
      "args": ["/abs/path/run_server.py"],
      "env": { "PIXABAY_API_KEY": "your-key-here" }
    }
  }
}
```

**3. Get a free API key** at https://pixabay.com/api/docs/ and replace the
placeholder. (Without it the server falls back to a shared, rate-limited demo
key — fine for a first test, not for real use.)

**4. Fully quit and reopen Claude Desktop.** You should see the pixabay tools
available. Ask it something like *"search Pixabay for mountain photos."*

Optional: set `PIXABAY_DATA_DIR` in the `env` block to control where the cache
and downloaded library live (default `~/.pixabay-plugin`).

### Troubleshooting

- **Tools don't appear:** you must *fully quit* Desktop (not just close the
  window) and reopen. Check the config file is valid JSON (no trailing commas).
- **Server fails to start:** re-run the setup script; it verifies the import.
  Desktop logs live next to the config file under `logs/`.
- **429 / rate limit:** you're on the shared demo key — add your own.

## Manual / dev install

```bash
pip install mcp
pip install -e .          # optional; exposes the `pixabay-mcp` command
export PIXABAY_API_KEY=your-key-here
python -m pixabay.server  # runs over stdio
```

## Tools

| Tool | Purpose |
|------|---------|
| `search_images` | Search images; returns slim hits + `result_id`. |
| `search_videos` | Search videos; each hit lists available renditions. |
| `paginate` | Next slim slice of a `result_id` (free from cache when possible). |
| `get_detail` | Full record for one hit, from cache (no API call). |
| `download_asset` | Save one asset server-side; returns path + attribution. |
| `library_list` / `library_remove` | Manage the persistent download library. |
| `status` | Show key/cache/library config. |

Image download sizes: `preview`, `web`, `large`, `fullhd`, `original`, `vector`
(the last three require full-API-access accounts). Video sizes: `large`,
`medium`, `small`, `tiny`.

## Layout

```
pixabay-mcp/
  run_server.py   path-independent launcher for MCP clients
  setup.sh        macOS/Linux one-command setup (venv + config)
  setup.ps1       Windows one-command setup (venv + config)
  pyproject.toml  packaging (optional `pip install -e .`)
  pixabay/
    config.py       key + paths (env-driven)
    client.py       stdlib HTTP, rate-limit backoff
    cache.py        24h disk cache, page-independent keys
    projections.py  slim dicts + tag trimming + attribution
    search.py       session orchestration (free cache pagination)
    library.py      download-to-server + manifest (dedup, attribution)
    server.py       FastMCP wrapper (the tools above)
```

Zero external dependencies except the `mcp` SDK; the core is pure standard library.
