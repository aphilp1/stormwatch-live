# StormWatch Cloud

The **public-web backend** for StormWatch Live. This is what lets visitors to the
GitHub Pages site use the "smart" tools (agents) without needing your laptop.

It is a **completely separate copy** of the backend logic. It does **not** touch or
replace `../mcp-server/`, which keeps powering Claude Desktop and your local app.

## What's here so far

- **Fire agent** (`/fire-agent?lat=..&lon=..`) — proof-of-concept, ported verbatim
  from the local `:3456` backend. Verified to return identical results.
- **Health check** (`/health`).

More agents (Flood, Nowcast, Combined) can be added the same way later.
WindNinja is intentionally **not** here — it needs heavy native compute and stays
a local-only feature for now.

## Test it on your own machine (no account, nothing goes online)

```powershell
cd stormwatch-cloud
npx wrangler dev            # runs at http://127.0.0.1:8787
# then in a browser or another terminal:
#   http://127.0.0.1:8787/health
#   http://127.0.0.1:8787/fire-agent?lat=34.05&lon=-118.25
```

Press Ctrl-C to stop it.

## Put it online (later — needs a free Cloudflare account)

```powershell
npx wrangler login         # opens browser, one-time
npx wrangler deploy        # publishes to https://stormwatch.<your-subdomain>.workers.dev
```

Only **after** it's deployed and you've tested the public URL would we point the
website at it — and even then, in a way that leaves the current site working if the
cloud backend is ever down.

## Safety rules

- Never commit a real email — the NWS contact string is a placeholder (public repo).
- This folder is independent: deleting it cannot break the local app or the live site.
