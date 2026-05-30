---
name: StormWatch recovery procedure
description: How to restore StormWatch files from the 2026-05-09 stability backup — the last known-good state with all 16 tools and stability fixes
type: project
originSessionId: c9f7fb6e-f1f7-461c-9a34-24f4e7e7eca6
---
# StormWatch Recovery — 2026-05-09 Stability Backup

The `-stability` backup is the **last known-good state** of the MCP server, with all fixes applied:
- EADDRINUSE crash fix
- Geocoding progressive fallback ("City State" formats)
- Tool 9 flight category computed fallback
- HTTP server startup logging
- HTTP veg validation

## Backup file locations

| Live file | Backup to restore from |
|-----------|------------------------|
| `C:\Users\aphil\Documents\Stormwatch\weather-alerts.html` | `weather-alerts.backup-2026-05-09.html` (same folder) |
| `C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js` | `mcp-server\index.backup-2026-05-09-stability.js` |
| `C:\Users\aphil\Documents\Stormwatch\mcp-server\package.json` | `mcp-server\package.backup-2026-05-09.json` |

## Recovery steps

### Restore the MCP server (index.js):
```powershell
Copy-Item "C:\Users\aphil\Documents\Stormwatch\mcp-server\index.backup-2026-05-09-stability.js" `
          "C:\Users\aphil\Documents\Stormwatch\mcp-server\index.js" -Force
```

### Restore the HTML app:
```powershell
Copy-Item "C:\Users\aphil\Documents\Stormwatch\weather-alerts.backup-2026-05-09.html" `
          "C:\Users\aphil\Documents\Stormwatch\weather-alerts.html" -Force
```

### After restoring index.js:
1. Fully quit Claude Desktop (system tray → Quit)
2. Wait ~10 seconds for Node processes to clear
3. Reopen Claude Desktop — it will load the restored index.js automatically
4. Verify: `Invoke-RestMethod "http://localhost:3456/health"` should return `{"status":"ok",...}`

## Why: What "stability" means here
The earlier backup `index-backup-2026-05-09.js` (no `-stability` suffix) is from the first pass of the session — before the EADDRINUSE fix and other stability work. Always prefer `-stability` for recovery.
