---
name: stormwatch-live-vision-and-roadmap
description: "Big-picture goals, strategic direction, and long-term roadmap for StormWatch Live and the broader AI-assisted weather intelligence platform"
metadata: 
  node_type: memory
  type: project
  originSessionId: 84bd3807-6e32-47ea-8dfd-3bcf9b24f334
---

## The Vision

StormWatch Live is not just a weather map. The goal is a fully intelligent, AI-powered situational awareness and forecasting platform — combining real-time data, conversational AI, model verification, and scalable agent architecture. Claude Code and Claude Chat are the primary builders and collaborators.

**Why this matters:** Understanding not just WHAT is happening (the map) but WHY it matters (the analysis, the forecast, the risk) — and eventually predicting it before it happens (forecasting agents).

---

## Roadmap — Priority Order

### 1. Chat Panel (MCP Integration in StormWatch)
Built-in chat window inside StormWatch Live. User asks weather questions; answers come from MCP server's 19 tools without leaving the app.
- POST to `localhost:3456/chat` endpoint
- Chat history panel in sidebar
- Contextually aware of what's on the map (current location, active layers)
**Why:** Closes the loop between seeing conditions and understanding them.

### 2. NSSL CAMs Verification Overlays
Wind LSRs, Tornado LSRs, Hail LSRs, NWS Warnings overlaid on the 4-panel CAMs viewer.
- First step: capture overlay image URLs from NSSL Network tab
- Likely pre-rendered transparent PNGs from NSSL server
**Why:** Verification is the core use case of the NSSL comparison tool — did the models actually get it right?

### 3. GitHub Repository ✓ DONE (2026-05-17)
Public repo at https://github.com/aphilp1/stormwatch-live
- Claude Code commits and pushes after every session
- Claude Chat fetches raw files via GitHub URL — no more uploads
- Full version history, three pre-GitHub backup sets also preserved locally

### 4. Continuous Improvement
Ongoing refinement of existing features based on real-world use:
- UI/UX polish as issues are found
- New data layers as NOAA/NWS/USGS APIs evolve
- Performance (preloading, caching, animation smoothness)
- Bug fixes surfaced through Claude Chat browser inspection

### 5. Accessibility
Make StormWatch usable for a broader audience:
- Keyboard navigation throughout
- Screen reader compatibility for alert panels
- Color-blind friendly palette options for severity colors
- Mobile/tablet responsive layout
**Why:** Weather information is critical infrastructure — it should be accessible to everyone.

### 6. Expanded MCP Servers and External Integrations
Scale beyond the current 19-tool server:
- **Additional MCP servers** for specialized domains (aviation weather, marine, space weather)
- **NVIDIA integration** — GPU-accelerated weather model visualization, AI/ML inference for nowcasting, diffusion models for ensemble spread
- **External server access** — connect to more NOAA, ECMWF, and private weather API endpoints
- **Complex data systems** — integrate high-resolution model output (HREF, NBM, GEFS) as they become accessible
**Why:** Each new data source compounds the analytical value of the platform.

### 7. Claude Code + Claude Chat as a Development System
Leverage the two-Claude workflow systematically:
- Claude Chat + Chrome integration: dynamically capture API responses, DOM structure, and network requests from live weather sites to reverse-engineer data formats and URL patterns
- Claude Code: implement, test, and maintain the codebase
- Structured handoff files (`bug-report.md`, `for-claude-chat.md`) as standard protocol
- GitHub as the shared codebase so neither instance is ever out of date
**Why:** The Chrome integration unlocks the ability to discover undocumented APIs (like NSSL overlay URLs) in minutes rather than hours.

### 8. Forecasting Agents (ON-DEMAND, map-triggered)
Claude is the reasoning engine. MCP tools are the data feeds. The agent orchestrates multiple tools, combines results, and produces a synthesized risk assessment with a "why it matters" explanation.

**Interaction model:**
- User clicks a point on the map → lat/lon captured → StormWatch sends to MCP server → agent gathers data from multiple sources → Claude synthesizes a briefing → result displayed in a panel
- Stretch goal: drag a bounding box for an area forecast instead of a single point (minimal extra compute — just API calls, not local processing)

**Build order:**
1. **Severe Weather / Nowcasting agent** — surface obs, SPC outlooks, NWS alerts, radar context, UH tracks → severe weather risk + developing threat narrative
2. **Fire Weather agent** — RAWS obs, KBDI, SPC fire outlook, red flag alerts → fire weather risk window + mechanism explanation
3. **Flood agent** — USGS river gauges, NWS flood alerts, soil moisture context → flooding risk + why it's developing

**What each agent does:**
- Calls 4-6 existing MCP tools for the target location
- Claude reasons over the combined data
- Returns: current conditions summary, threat level, why-it-matters explanation, confidence note
- Displayed in a dedicated briefing panel in StormWatch (not requiring Chat Panel to be built first)

**Built on existing tools:** `get_weather_briefing`, `get_all_hazards_briefing`, `get_river_summary`, `get_metar`, `get_fire_weather`, `get_raws_observations`
**Why:** Moving from reactive (showing current conditions) to proactive (anticipating and explaining what's coming).

---

## Collaboration Architecture (Current + Target)

| Today | Target |
|-------|--------|
| User manually transfers info between Claude Code and Claude Chat | GitHub repo = shared codebase, always current |
| weather-alerts.html uploaded to Claude Chat Project | Auto-updated via git push |
| Claude Chat inspects browser manually | Claude Chat + Chrome integration = dynamic API discovery |
| MCP server runs 19 tools locally | Multiple MCP servers, external integrations, NVIDIA acceleration |
| Chat requires Claude Desktop | Built-in chat panel in StormWatch itself |

---

## Key Insight

The platform's value compounds with each addition. More data sources → better context. Better context → more meaningful analysis. Conversational AI on top of the map → the "why this matters" layer that transforms raw weather data into actionable intelligence. Forecasting agents → proactive rather than reactive awareness.

The goal is not just a better weather app. It is an AI-native weather intelligence platform built collaboratively by a human and two Claude instances.
