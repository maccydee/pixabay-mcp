# One-command setup for Windows: isolated venv + MCP SDK, then prints the exact
# Claude Desktop config block with your real absolute paths.
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "-> Creating virtual environment (.venv) ..."
python -m venv .venv

Write-Host "-> Installing the MCP SDK ..."
& ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install --quiet "mcp>=1.2.0"

Write-Host "-> Verifying the server imports ..."
& ".\.venv\Scripts\python.exe" -c "import pixabay.server"
Write-Host "  ok."

$py = Join-Path $here ".venv\Scripts\python.exe"
$run = Join-Path $here "run_server.py"

@"

------------------------------------------------------------------------------
Setup complete. Paste this into your Claude Desktop config:

  %APPDATA%\Claude\claude_desktop_config.json

If the file already has an "mcpServers" object, add only the "pixabay" entry.
------------------------------------------------------------------------------

{
  "mcpServers": {
    "pixabay": {
      "command": "$($py -replace '\\','\\')",
      "args": ["$($run -replace '\\','\\')"],
      "env": { "PIXABAY_API_KEY": "your-key-here" }
    }
  }
}

Then fully quit and reopen Claude Desktop. Get a free key at
https://pixabay.com/api/docs/ (a demo key is used if you leave the placeholder).
"@ | Write-Host
