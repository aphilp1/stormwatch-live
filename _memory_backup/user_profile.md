---
name: User profile
description: Who the user is, their technical level, their machine, and how to work with them
type: user
originSessionId: 12ddcaa0-0958-45bc-84d2-2f764a3351bd
---
- Windows 11 Home on a modest Dell laptop (not a powerhouse — avoid heavy local processing)
- Non-technical / hobbyist level: needs step-by-step instructions for anything outside the app itself (installing Python, running commands, etc.)
- Weather enthusiast building StormWatch Live as a personal project — vision has grown significantly beyond a hobby app
- Cares deeply about the end-user experience and visual quality of the app
- Makes decisions collaboratively — presents options, user chooses direction
- Python 3.14.4 installed as of 2026-05-03 (installed during this project)
- Runs StormWatch via local HTTP server (`python -m http.server 8000`) when USGS features needed; otherwise opens file directly
- Uses Claude Chat alongside Claude Code: Chat inspects browser/DOM, Code writes and maintains files. Now using Claude Chat Projects to share weather-alerts.html and mcp-server/index.js
- Claude Chat has Chrome integration for dynamic page/API inspection — use this for discovering undocumented API patterns (e.g. NSSL overlay URLs)
- **Expanded vision (as of 2026-05-17):** StormWatch is becoming an AI-native weather intelligence platform. Goals include: built-in chat panel (MCP integration), NSSL verification overlays, GitHub version control, accessibility improvements, additional MCP servers, NVIDIA/ML integration, and autonomous forecasting agents. See [[project_vision]] for full roadmap.
- Motivated by the "why this matters" layer — not just showing data but explaining the meteorological significance and eventually predicting outcomes proactively.
