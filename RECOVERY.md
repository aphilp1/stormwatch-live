# StormWatch Live — Recovery Runbook

"My laptop died / I'm on a fresh machine — how do I get StormWatch back?"

Everything needed to rebuild is in the public GitHub repo. The only things NOT in
Git are: `node_modules/` (reinstalled), local backup files (disposable), and
external tools (WindNinja, Python) which you install separately.

- **Repo:** https://github.com/aphilp1/stormwatch-live
- **Live public site (no local setup needed):** https://aphilp1.github.io/stormwatch-live/

---

## Two layers to restore

| Layer | What it is | Needs |
|-------|------------|-------|
| **A. The web app** | `weather-alerts.html` served locally | Python (any 3.x) |
| **B. The MCP backend** | `mcp-server/` — agents, WindNinja, smoke, AQ | Node ≥ 18, optionally WindNinja CLI |

The public GitHub Pages site works with neither installed (localhost-only
features gracefully degrade). Layers A + B are only for the full local experience.

---

## Full rebuild (step by step)

```powershell
# 0. Prerequisites
#    - Python 3.x         https://www.python.org/downloads/
#    - Node.js >= 18      https://nodejs.org/
#    - (optional) WindNinja CLI  https://www.firelab.org/project/windninja

# 1. Clone the repo
cd C:\Users\aphil\Documents
git clone https://github.com/aphilp1/stormwatch-live Stormwatch
cd Stormwatch

# 2. Rebuild the MCP backend
cd mcp-server
npm ci                          # restores exact deps from package-lock.json
cd ..

# 3. Register the MCP server with Claude Desktop
#    Copy mcp-server\claude_desktop_config.example.json into
#    %APPDATA%\Claude\claude_desktop_config.json  (fix the path to index.js),
#    then restart Claude Desktop.  Details: mcp-server\README.md

# 4. Launch the app
.\start-stormwatch.ps1          # serves :8001 + opens weather-alerts.html
```

That's it. Claude Desktop launches `mcp-server\index.js` (which also binds the
:3456 HTTP backend); `start-stormwatch.ps1` serves the page and opens it.

---

## Verify it worked

```powershell
curl http://127.0.0.1:3456/health          # → 200  (MCP backend up)
# In the browser: open http://localhost:8001/weather-alerts.html
# Fire/Flood/Nowcast agents should return data (they call :3456).
```

If agents fail but the map loads: you're almost certainly on the wrong port or
:3456 isn't up. **Check the browser is on the live port before diagnosing code**
— a stale port has masqueraded as a "code regression" before.

---

## What is NOT in Git (and why that's fine)

- `mcp-server/node_modules/` — reinstalled by `npm ci`.
- `*.backup-*`, `*-backup-*.tgz` — local safety copies; Git history *is* the backup.
- WindNinja CLI, Python, Node — external installs, not app code.
- Real NWS contact email — intentionally kept out (repo is public); a placeholder
  is used everywhere.

---

## Key local paths (this machine)

| Path | What |
|------|------|
| `C:\Users\aphil\Documents\Stormwatch\` | Project root |
| `mcp-server\index.js` | MCP server (~32 tools) + :3456 HTTP backend |
| `weather-alerts.html` | The app (single-file front end) |
| `%APPDATA%\Claude\claude_desktop_config.json` | MCP registration Claude Desktop reads |
| `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe` | WindNinja CLI (default path) |
| `C:\temp\windninja_cache` | WindNinja scratch/output |
