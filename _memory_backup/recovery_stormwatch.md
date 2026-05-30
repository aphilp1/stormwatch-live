---
name: stormwatch-recovery-procedure
description: How to restore StormWatch from pre-GitHub backups (2026-05-17) — three independent backup sets. Also covers how to abort GitHub setup without losing anything.
metadata: 
  node_type: memory
  type: project
  originSessionId: 84bd3807-6e32-47ea-8dfd-3bcf9b24f334
---

# StormWatch Recovery — Pre-GitHub Backup (2026-05-17)

**Three independent backup sets, all taken May 17 at 12:46.**
Sizes match originals: weather-alerts.html = 270K, index.js = 76K.

## Backup locations (three independent copies)

| Location | Folder / Files |
|----------|----------------|
| **Set 1** — in Stormwatch folder | `weather-alerts.PRE-GITHUB-2026-05-17.html`, `mcp-server/index.PRE-GITHUB-2026-05-17.js`, `package.PRE-GITHUB-2026-05-17.json`, `package-lock.PRE-GITHUB-2026-05-17.json`, `nssl_cams_viewer.PRE-GITHUB-2026-05-17.html` |
| **Set 2** — Desktop | `C:\Users\aphil\Desktop\StormWatch-Backup-PreGitHub-2026-05-17\` (all 5 files) |
| **Set 3** — Documents | `C:\Users\aphil\Documents\StormWatch-Backup-PreGitHub-2026-05-17\` (all 5 files) |

## Restore from pre-GitHub backup (PowerShell)

```powershell
# Restore main app
Copy-Item "C:\Users\aphil\Documents\StormWatch-Backup-PreGitHub-2026-05-17\weather-alerts.html" `
          "C:\Users\aphil\Documents\Stormwatch\weather-alerts.html" -Force

# Restore MCP server
Copy-Item "C:\Users\aphil\Documents\StormWatch-Backup-PreGitHub-2026-05-17\index.js" `
          "C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js" -Force

# Restore package files (usually not needed)
Copy-Item "C:\Users\aphil\Documents\StormWatch-Backup-PreGitHub-2026-05-17\package.json" `
          "C:\Users\aphil\Documents\Stormwatch\mcp-server\package.json" -Force
Copy-Item "C:\Users\aphil\Documents\StormWatch-Backup-PreGitHub-2026-05-17\package-lock.json" `
          "C:\Users\aphil\Documents\Stormwatch\mcp-server\package-lock.json" -Force
```

After restoring index.js:
1. Fully quit Claude Desktop (system tray → Quit)
2. Wait ~10 seconds
3. Reopen Claude Desktop — it reloads index.js automatically
4. Verify: `Invoke-RestMethod "http://localhost:3456/health"` → should return `{"status":"ok",...}`

## How to abort GitHub setup with zero damage

**GitHub is version control only. It has no effect on how the app runs locally.**

If anything goes wrong during GitHub setup:

### Option A — Remove git entirely (nuclear, safe)
```powershell
Remove-Item -Recurse -Force "C:\Users\aphil\Documents\Stormwatch\.git"
```
This removes all git history and leaves every file exactly as it was. The app, MCP server, WindNinja, and HTTP server all continue to work — git is not in their path at all.

### Option B — Just stop and walk away
If GitHub setup stalls or errors out mid-way, nothing bad happens until a `git push` completes. Files on your machine are never altered by git init or git commit. You can simply close the terminal and everything is unchanged.

### What GitHub does NOT touch
- `weather-alerts.html` contents
- `mcp-server/index.js` and Node.js / MCP tools
- WindNinja executable and cache at `C:\temp\windninja_cache`
- The HTTP server (`python -m http.server 8000`)
- Claude Desktop MCP connection
- Any local file functionality

## Local-only startup (no GitHub needed, ever)

```powershell
# Start HTTP server (for USGS layer)
cd "C:\Users\aphil\Documents\Stormwatch"
python -m http.server 8000

# MCP server starts automatically when Claude Desktop opens
# Verify it's running:
Invoke-RestMethod "http://localhost:3456/health"
```

---

# Legacy: 2026-05-09 Stability Backup

The `-stability` backup (MCP server only) is still present:
`mcp-server\index.backup-2026-05-09-stability.js`

That backup predates: WindNinja overlay, USGS gauges layer, NSSL CAMs viewer, Maps sidebar context panel, all Claude Chat code-review fixes. Use Pre-GitHub backup for any recovery after 2026-05-17.
