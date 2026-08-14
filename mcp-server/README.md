# StormWatch MCP Server

Weather tools for Claude (Model Context Protocol). This is the local backend that
powers StormWatch Live's localhost-only features: the 4 forecasting agents
(Nowcast / Fire / Flood / Combined), WindNinja terrain-wind runs, HMS smoke, and
AirNow air quality. The public GitHub Pages site runs without it (those features
gracefully degrade via `MCP_LOCAL`).

- **Runtime:** Node.js ≥ 18 (developed on v24)
- **Entry point:** `index.js` (stdio MCP server, ~32 tools)
- **Also serves:** a small HTTP API on `127.0.0.1:3456` for the browser app to call

---

## How it's wired

```
Claude Desktop ──stdio──▶ node index.js  (MCP: ~32 tools)
                                  │
weather-alerts.html ──HTTP──▶ 127.0.0.1:3456  (agents, WindNinja, etc.)
```

Two independent surfaces from the same process:
1. **MCP over stdio** — Claude Desktop launches `node index.js` and talks to it directly.
2. **HTTP on :3456** — the browser app (`weather-alerts.html`) fetches agent/WindNinja
   results. If :3456 is already in use, the process skips HTTP and all stdio tools
   still work.

---

## Rebuild from scratch (fresh machine)

```powershell
# 1. Get the code (node_modules is gitignored — do NOT copy it)
git clone https://github.com/aphilp1/stormwatch-live
cd stormwatch-live/mcp-server

# 2. Install dependencies from the lockfile
npm ci          # exact versions from package-lock.json
# (use `npm install` only if there is no lockfile)

# 3. (Optional) install WindNinja CLI if you want terrain-wind tools
#    https://www.firelab.org/project/windninja  → default path below

# 4. Register with Claude Desktop (see config example below), then restart Desktop
```

Dependencies (`package.json`): `@modelcontextprotocol/sdk`, `zod`.

---

## Configuration (environment variables)

All optional — the server has working defaults for this machine. See `.env.example`.

| Variable          | Default                                                  | Purpose |
|-------------------|----------------------------------------------------------|---------|
| `WINDNINJA_CLI`   | `C:\WindNinja\WindNinja-3.12.2\bin\WindNinja_cli.exe`    | Path to WindNinja CLI. If missing, WindNinja tools warn and fail gracefully; everything else works. |
| `WINDNINJA_CACHE` | `C:\temp\windninja_cache`                                | Scratch dir for DEM tiles + WindNinja output (auto-created). |
| `NWS_EMAIL`       | a GitHub URL placeholder                                 | Contact string in the NWS API User-Agent header. **Keep any committed copy a placeholder** — never commit a real email (repo is public). |

> Note: Claude Desktop does not read `.env` files automatically. To override a
> default, either edit the defaults at the top of `index.js`, or add an `env`
> block to the Desktop config (see the example file).

---

## Register with Claude Desktop

Config file location (Windows): `%APPDATA%\Claude\claude_desktop_config.json`

Minimal registration — see `claude_desktop_config.example.json`:

```json
{
  "mcpServers": {
    "stormwatch": {
      "command": "node",
      "args": ["C:\\Users\\aphil\\Documents\\Stormwatch\\mcp-server\\index.js"]
    }
  }
}
```

Restart Claude Desktop after editing. On boot the server logs (to stderr) whether
it found the WindNinja CLI and whether it bound port 3456.

---

## Health check

```powershell
# Is the HTTP backend up?
curl http://127.0.0.1:3456/health          # → 200

# Run the MCP server standalone (Ctrl-C to stop); watch startup log lines:
node index.js
# [stormwatch] WindNinja CLI confirmed at ...
# [stormwatch] HTTP server listening on 127.0.0.1:3456
```

---

## Related files

- `../start-stormwatch.ps1` — launches the app server (:8001) and checks :3456.
- `../RECOVERY.md` — full "my laptop died" rebuild runbook (app + MCP).
