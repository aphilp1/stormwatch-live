# StormWatch — Alert Coverage & Color Audit

*Session: 2026-08-14 → 2026-08-15. Reference doc — not a resume anchor; read
`PICKUP_TOMORROW.md` for that.*

## 1. What StormWatch shows

Alert ingestion (`weather-alerts.html:2518`) is the **unfiltered** NWS Active
Alerts feed:

```
NWS_ALERTS = 'https://api.weather.gov/alerts/active?status=actual'
```

Every alert type NWS issues — Warnings, Watches, Advisories, Statements,
Emergencies, "Other" — comes through. Nothing is dropped at ingestion. An
alert type without a custom style still renders, via a generic severity-color
fallback (`SEV_FB`: Extreme/Severe/Moderate/Minor/Unknown,
`weather-alerts.html:2678`).

## 2. Explicitly-styled alert types (58, `ESTYLES`, `weather-alerts.html:2612-2671`)

**Tornado / Severe Storms:** Tornado Warning, Tornado Emergency, Tornado
Watch, Severe Thunderstorm Warning, Severe Thunderstorm Watch, Special Marine
Warning, Extreme Wind Warning

**Flood:** Flash Flood Emergency, Flash Flood Warning, Flash Flood Watch,
Flash Flood Statement, Flood Warning, Flood Watch, Flood Statement, Flood
Advisory, Coastal Flood Warning, Coastal Flood Watch, Coastal Flood Advisory

**Winter:** Blizzard Warning, Ice Storm Warning, Winter Storm Warning, Winter
Storm Watch, Winter Weather Advisory, Heavy Snow Warning, Heavy Snow Watch,
Lake Effect Snow Warning, Lake Effect Snow Watch, Lake Effect Snow Advisory,
Snow Squall Warning, Freezing Rain Advisory, Freezing Drizzle Advisory, Frost
Advisory, Freeze Warning, Freeze Watch, Wind Chill Warning, Wind Chill Watch,
Wind Chill Advisory

**Wind:** High Wind Warning, High Wind Watch, Wind Advisory

**Fire:** Red Flag Warning, Fire Weather Watch

**Heat:** Excessive Heat Warning, Excessive Heat Watch, Heat Advisory

**Tropical / Marine:** Hurricane Warning, Hurricane Watch, Tropical Storm
Warning, Tropical Storm Watch, Storm Surge Warning, Storm Surge Watch

**Visibility / Air:** Dense Fog Advisory, Dense Smoke Advisory, Dust Storm
Warning, Blowing Dust Advisory, Air Quality Alert

**Tsunami:** Tsunami Warning, Tsunami Watch

**Other:** Special Weather Statement

Anything outside this list (Avalanche Warning, Gale Warning, Small Craft
Advisory, etc.) still displays on the map — via the severity fallback color,
not a bespoke one.

## 3. NWS severe-weather product coverage gap assessment (2026-08-14)

Full assessment compared the app against the universe of NWS/SPC/WPC/NHC
severe-weather products. **All 3 gaps found have since been shipped**
(commits `9f36242`, `48dc51a` — pushed and live):

| Gap | Status |
|---|---|
| SPC Mesoscale Discussions | ✅ Shipped — `lyr-mcd` toggle, live SPC feed |
| WPC Excessive Rainfall Outlook | ✅ Shipped — `lyr-ero` toggle, Day 1-5 |
| Live Local Storm Reports | ✅ Shipped — `lyr-lsr` toggle, 3h/6h/12h/24h window, via IEM |

Tropical cyclone cone/track graphics are intentionally **not** in StormWatch
— that's RapidWatch's domain (a separate project). Storm-based warning
polygons, MRMS reflectivity/QPE, and everything else in the core
severe-weather domain were already covered pre-audit.

## 4. Alert color scheme vs. official NWS table (2026-08-15)

Compared `ESTYLES` (58 types, §2 above) against the official NWS
Watch/Warning/Advisory color reference
(`weather.gov/media/nws/WWA_Changes_10124.pdf`, 111 products, priority-ordered).

**Decision: leave as-is.** Confirmed with Alex 2026-08-15 — StormWatch's
palette is an intentional, internally-consistent custom scheme (graded for
contrast/readability on the app's basemap), not meant to copy the official
table. Do not "fix" these to match NWS in a future session without being
asked again.

### Exact / near-exact matches (11)

| Type | Official | Ours |
|---|---|---|
| Tornado Warning | `#FF0000` | `#ff0000` |
| Blizzard Warning | `#FF4500` | `#ff4500` |
| High Wind Warning | `#DAA520` | `#daa520` |
| High Wind Watch | `#B8860B` | `#b8860b` |
| Wind Advisory | `#D2B48C` | `#d2b48c` |
| Red Flag Warning | `#FF1493` | `#ff1493` |
| Hurricane Watch | `#FF00FF` | `#ff00ff` |
| Dense Fog Advisory | `#708090` | `#708090` |
| Blowing Dust Advisory | `#BDB76B` | `#bdb76b` |
| Winter Weather Advisory | `#7B68EE` | `#7b68ee` |
| Heat Advisory | `#FF7F50` | `#ff7050` |

### Major mismatches — different color family entirely (11)

| Type | Official | Ours |
|---|---|---|
| Flash Flood Warning | dark red `#8B0000` | green `#00bb44` |
| Winter Storm Warning | hot pink `#FF69B4` | teal `#00bbcc` |
| Snow Squall Warning | magenta `#C71585` | blue `#8899ff` |
| Fire Weather Watch | pale tan `#FFDEAD` | dark red `#cc3366` |
| Tsunami Warning | tomato `#FD6347` | blue `#0044ff` |
| Tsunami Watch | fuchsia `#FF00FF` | blue `#0033cc` |
| Tropical Storm Warning | firebrick `#B22222` | teal `#00dddd` |
| Tropical Storm Watch | light coral `#F08080` | blue `#00aadd` |
| Excessive Heat Watch | maroon `#800000` | orange `#ff4422` |
| Severe Thunderstorm Watch | pale violet-red `#DB7093` | olive/gold `#ddaa00` |
| Dense Smoke Advisory | khaki `#F0E68C` | brown `#aa8855` |

### Minor / shade-level mismatches (same hue family, different exact value)

Severe Thunderstorm Warning (official `#FFA500` vs ours `#ff8c00`), Flood
Warning (`#00FF00` lime vs our dark `#009933`), Coastal Flood Watch
(`#66CDAA` vs our `#33aa33`), Hurricane Warning (`#DC143C` crimson vs our
pure `#ff0000`), Ice Storm Warning (`#8B008B` vs our `#aa00aa`), Storm Surge
Warning (`#B524F7` vs our `#bb33ee`), Excessive Heat Warning (`#C71585` vs
our `#cc2244`), Air Quality Alert (`#808080` gray vs our `#aa8833` olive).

## Related

- Memory: `stormwatch-alert-colors-not-nws-official` — the standing rule not
  to re-flag this as a bug.
- `PICKUP_TOMORROW.md` — session resume anchor, has the fuller 2026-08-14
  session log (health check, cleanup, Fire Risk probe fix, smoke-test infra).
