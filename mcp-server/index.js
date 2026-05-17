import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { execFile } from "child_process";
import { promisify } from "util";
import { mkdirSync, existsSync, readFileSync, unlinkSync } from "fs";
import { createServer } from "http";

const execFileAsync = promisify(execFile);
const WINDNINJA_CLI = process.env.WINDNINJA_CLI ?? "C:\\WindNinja\\WindNinja-3.12.2\\bin\\WindNinja_cli.exe";
const WINDNINJA_CACHE = process.env.WINDNINJA_CACHE ?? "C:\\temp\\windninja_cache";

const server = new McpServer({
  name: "stormwatch",
  version: "4.0.0",
});

const NWS_HEADERS = { "User-Agent": `StormWatchMCP/2.0 (${process.env.NWS_EMAIL ?? "+https://github.com/aphilp1/stormwatch-live"})` };

function distKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function dirToCardinal(deg) {
  const dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  return dirs[Math.round(deg / 22.5) % 16];
}

// Geocoding helper — handles city names, "City, ST", "City ST", "City StateName" formats, and raw coordinates
async function geocode(location) {
  // Accept raw coordinates: "34.74,-98.69" or "34.74N 98.69W" or "34.74 -98.69"
  const coordDec = location.match(/^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$/);
  if (coordDec) {
    const lat = parseFloat(coordDec[1]), lon = parseFloat(coordDec[2]);
    return { lat, lon, name: `${lat.toFixed(4)}, ${lon.toFixed(4)}` };
  }
  const coordNS = location.match(/^(\d+\.?\d*)\s*([NS])[,\s]+(\d+\.?\d*)\s*([EW])$/i);
  if (coordNS) {
    const lat = parseFloat(coordNS[1]) * (coordNS[2].toUpperCase() === 'S' ? -1 : 1);
    const lon = parseFloat(coordNS[3]) * (coordNS[4].toUpperCase() === 'W' ? -1 : 1);
    return { lat, lon, name: `${coordNS[1]}°${coordNS[2].toUpperCase()}, ${coordNS[3]}°${coordNS[4].toUpperCase()}` };
  }

  // Build a progressive list of queries: full string → strip comma suffix → strip last word → strip last 2 words
  // Handles: "Tulsa, OK", "Dallas TX", "Memphis Tennessee", "Albuquerque New Mexico"
  const words = location.trim().split(/\s+/);
  const candidates = [location.trim()];
  const noCommaSuffix = location.replace(/,\s*.+$/, '').trim();
  if (noCommaSuffix && noCommaSuffix !== location.trim()) candidates.push(noCommaSuffix);
  if (words.length >= 2) candidates.push(words.slice(0, -1).join(' '));
  if (words.length >= 3) candidates.push(words.slice(0, -2).join(' '));

  const seen = new Set();
  const tries = candidates.filter(c => c.length > 0 && !seen.has(c) && seen.add(c));

  for (const query of tries) {
    const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&language=en&format=json`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
    const data = await res.json();
    const r = data.results?.[0];
    if (r) return { lat: r.latitude, lon: r.longitude, name: `${r.name}, ${r.admin1 ?? r.country_code}` };
  }

  throw new Error(`Location not found: "${location}". For mountain ranges or parks, use the nearest town name or decimal coordinates like "34.74,-98.69".`);
}

const WMO = {
  0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
  45:"Foggy",48:"Icy fog",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",
  61:"Light rain",63:"Rain",65:"Heavy rain",
  71:"Light snow",73:"Snow",75:"Heavy snow",77:"Snow grains",
  80:"Rain showers",81:"Heavy showers",82:"Violent showers",
  85:"Snow showers",86:"Heavy snow showers",
  95:"Thunderstorm",96:"Thunderstorm w/ hail",99:"Severe thunderstorm",
};

const AQI_CATS = [
  { max: 50,       label: "Good",                          emoji: "🟢" },
  { max: 100,      label: "Moderate",                      emoji: "🟡" },
  { max: 150,      label: "Unhealthy for Sensitive Groups", emoji: "🟠" },
  { max: 200,      label: "Unhealthy",                     emoji: "🔴" },
  { max: 300,      label: "Very Unhealthy",                 emoji: "🟣" },
  { max: Infinity, label: "Hazardous",                     emoji: "⚫" },
];

// ── Tool 1: Active NWS alerts by state ──────────────────────────────────────

server.tool(
  "get_active_alerts",
  "Get currently active NWS weather alerts for a US state",
  {
    state: z.string().length(2).toUpperCase().describe("Two-letter US state code, e.g. OK, TX, FL"),
  },
  async ({ state }) => {
    const url = `https://api.weather.gov/alerts/active?area=${state.toUpperCase()}&status=actual`;
    const res = await fetch(url, { headers: NWS_HEADERS });
    if (!res.ok) throw new Error(`NWS API error: ${res.status}`);
    const data = await res.json();

    const alerts = data.features ?? [];
    if (alerts.length === 0) {
      return { content: [{ type: "text", text: `No active weather alerts for ${state.toUpperCase()}.` }] };
    }

    const lines = alerts.map((f) => {
      const p = f.properties;
      const expires = p.expires ? new Date(p.expires).toLocaleString() : "unknown";
      return `• ${p.event} — ${p.areaDesc}\n  Severity: ${p.severity} | Expires: ${expires}\n  ${p.headline ?? ""}`.trim();
    });

    return {
      content: [{
        type: "text",
        text: `${alerts.length} active alert${alerts.length !== 1 ? "s" : ""} for ${state.toUpperCase()}:\n\n${lines.join("\n\n")}`,
      }],
    };
  }
);

// ── Tool 2: SPC severe weather outlook ──────────────────────────────────────

server.tool(
  "get_severe_outlook",
  "Get the SPC severe thunderstorm outlook for Day 1 (today) or Day 2 (tomorrow) with geographic narrative",
  {
    day: z.number().int().min(1).max(2).describe("Forecast day: 1 for today, 2 for tomorrow"),
  },
  async ({ day }) => {
    const url = `https://www.spc.noaa.gov/products/outlook/day${day}otlk.txt`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`SPC text product error: ${res.status}`);
    const text = await res.text();

    const body = text.split("&&")[0] ?? text;
    const lines = body.split("\n").map(l => l.trim()).filter(Boolean);
    const start = lines.findIndex(l => l.includes("CONVECTIVE OUTLOOK") || l.includes("RISK") || l.includes("THERE IS"));
    const content = lines.slice(Math.max(0, start)).join("\n");

    const dayLabel = day === 1 ? "Today (Day 1)" : "Tomorrow (Day 2)";
    return {
      content: [{
        type: "text",
        text: `SPC Severe Weather Outlook — ${dayLabel}:\n\n${content}\n\nSource: Storm Prediction Center (spc.noaa.gov)`,
      }],
    };
  }
);

// ── Tool 3: Nearest NWS flood gauge ─────────────────────────────────────────

server.tool(
  "get_nearest_gauge",
  "Find the nearest NWS flood gauge to a city or location and return its current river stage and flood status",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Tulsa OK', 'Memphis Tennessee'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const url = `https://mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query?geometry=${lon},${lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&distance=75&units=esriSRUnit_StatuteMile&outFields=gaugelid,location,observed,status,units,waterbody,state,obstime&returnGeometry=true&f=json`;
    const res = await fetch(url, { headers: NWS_HEADERS });
    if (!res.ok) throw new Error(`Gauge MapServer error: ${res.status}`);
    const data = await res.json();

    const features = data.features ?? [];
    if (features.length === 0) {
      return { content: [{ type: "text", text: `No flood gauges found within 75 miles of ${placeName}. Try a location closer to a major river.` }] };
    }

    let nearest = null, nearestDist = Infinity;
    for (const f of features) {
      const gLon = f.geometry?.x, gLat = f.geometry?.y;
      if (gLat == null || gLon == null) continue;
      const d = distKm(lat, lon, gLat, gLon);
      if (d < nearestDist) { nearestDist = d; nearest = f; }
    }
    if (!nearest) return { content: [{ type: "text", text: `Gauge data found but geometry was missing.` }] };

    const a = nearest.attributes;
    const lid = a.gaugelid?.toLowerCase();

    let extra = "";
    try {
      const detail = await fetch(`https://api.water.noaa.gov/nwps/v1/gauges/${lid}`, { headers: NWS_HEADERS });
      if (detail.ok) {
        const g = await detail.json();
        const obs = g.status?.observed;
        const fcst = g.status?.forecast;
        const thr = g.flood?.categories;
        if (fcst?.floodCategory) extra += `\nForecast: ${fcst.floodCategory} (${fcst.primary ?? "?"} ${obs?.primaryUnit ?? "ft"} by ${fcst.validTime ? new Date(fcst.validTime).toLocaleString() : "?"})`;
        if (thr) extra += `\nFlood stages — Minor: ${thr.minor?.stage ?? "?"} ft | Moderate: ${thr.moderate?.stage ?? "?"} ft | Major: ${thr.major?.stage ?? "?"} ft`;
      }
    } catch (_) {}

    const stage = a.observed != null ? `${a.observed} ${a.units ?? "ft"}` : "unknown";
    const status = a.status ?? "unknown";
    const waterbody = a.waterbody ? ` on the ${a.waterbody}` : "";

    return {
      content: [{
        type: "text",
        text: `Nearest gauge to ${placeName}: ${a.location}${waterbody} (${lid?.toUpperCase()})\nDistance: ${nearestDist.toFixed(1)} km away\nCurrent stage: ${stage}\nFlood status: ${status}\nLast observed: ${a.obstime ?? "unknown"}${extra}`,
      }],
    };
  }
);

// ── Tool 4: Point weather forecast ──────────────────────────────────────────

server.tool(
  "get_point_forecast",
  "Get an hourly weather forecast for any city or location — temperature, precipitation, wind, and weather conditions",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Dallas TX', 'Denver Colorado'"),
    hours: z.number().int().min(1).max(24).default(12).describe("Number of hours to show (1–24, default 12)"),
  },
  async ({ location, hours }) => {
    const { lat, lon, name: placeName } = await geocode(location);
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=temperature_2m,precipitation,windspeed_10m,winddirection_10m,weathercode&forecast_days=2&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&models=best_match`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Forecast API error: ${res.status}`);
    const data = await res.json();

    const h = data.hourly;
    const now = new Date();
    const startIdx = h.time.findIndex(t => new Date(t) >= now);
    const idx = startIdx === -1 ? 0 : startIdx;

    const lines = [];
    for (let i = idx; i < Math.min(idx + hours, h.time.length); i++) {
      const time = new Date(h.time[i]).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      const temp = h.temperature_2m[i] != null ? `${Math.round(h.temperature_2m[i])}°F` : "?";
      const wind = h.windspeed_10m[i] != null ? `${Math.round(h.windspeed_10m[i])} mph` : "?";
      const precip = h.precipitation[i] > 0 ? ` | Precip: ${h.precipitation[i].toFixed(2)}"` : "";
      const cond = WMO[h.weathercode[i]] ?? `Code ${h.weathercode[i]}`;
      lines.push(`${time}: ${temp}, ${cond}, Wind ${wind}${precip}`);
    }

    return {
      content: [{
        type: "text",
        text: `${hours}-hour forecast for ${placeName}:\n\n${lines.join("\n")}`,
      }],
    };
  }
);

// ── Tool 5: SPC fire weather outlook ────────────────────────────────────────

server.tool(
  "get_fire_weather_outlook",
  "Get the SPC fire weather outlook for Day 1 (today) or Day 2 (tomorrow) — shows Elevated, Critical, and Extreme fire weather risk areas with narrative",
  {
    day: z.number().int().min(1).max(2).describe("Forecast day: 1 for today, 2 for tomorrow"),
  },
  async ({ day }) => {
    // SPC fire weather text — try both known URL patterns
    const urls = [
      `https://www.spc.noaa.gov/products/fire_weather/fwdy${day}.txt`,
      `https://www.spc.noaa.gov/products/fire_weather/fwdy0${day}.txt`,
    ];

    let text = null;
    for (const url of urls) {
      try {
        const res = await fetch(url);
        if (res.ok) { text = await res.text(); break; }
      } catch (_) {}
    }

    if (!text) {
      const dayLabel = day === 1 ? "Today (Day 1)" : "Tomorrow (Day 2)";
      return {
        content: [{
          type: "text",
          text: `SPC Fire Weather Outlook — ${dayLabel}:\n\nThe fire weather outlook text product is not currently available. This may mean:\n• The outlook has not yet been issued for today (SPC typically issues at ~06 UTC and updates ~18 UTC)\n• There are no significant fire weather concerns at this time\n\nCheck https://www.spc.noaa.gov/products/fire_weather/ for the latest information.`,
        }],
      };
    }

    const body = text.split("&&")[0] ?? text;
    const lines = body.split("\n").map(l => l.trim()).filter(Boolean);
    const start = lines.findIndex(l => /FIRE WEATHER|ELEVATED|CRITICAL|NO CRITICAL|THERE IS/.test(l));
    const content = lines.slice(Math.max(0, start)).join("\n");

    const dayLabel = day === 1 ? "Today (Day 1)" : "Tomorrow (Day 2)";
    return {
      content: [{
        type: "text",
        text: `SPC Fire Weather Outlook — ${dayLabel}:\n\n${content}\n\nSource: Storm Prediction Center (spc.noaa.gov)`,
      }],
    };
  }
);

// ── Tool 6: SPC storm reports ────────────────────────────────────────────────

server.tool(
  "get_storm_reports",
  "Get today's actual storm reports from the SPC — confirmed tornadoes, large hail, and damaging wind events. Optionally filter by state.",
  {
    state: z.string().optional().describe("Optional two-letter state code to filter (e.g. TX, OK). Leave blank for all US reports."),
  },
  async ({ state }) => {
    const url = "https://www.spc.noaa.gov/climo/reports/today.csv";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`SPC reports error: ${res.status}`);
    const text = await res.text();

    const lines = text.split("\n").filter(l => l.trim());
    if (lines.length < 2) return { content: [{ type: "text", text: "No storm reports yet today." }] };

    const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
    const rows = lines.slice(1).map(l => {
      const cols = l.split(",");
      const obj = {};
      headers.forEach((h, i) => obj[h] = cols[i]?.trim() ?? "");
      return obj;
    }).filter(r => r.type);

    const filtered = state ? rows.filter(r => r.st?.toUpperCase() === state.toUpperCase()) : rows;

    if (filtered.length === 0) {
      return { content: [{ type: "text", text: state ? `No storm reports for ${state.toUpperCase()} today.` : "No storm reports today." }] };
    }

    const tornadoes = filtered.filter(r => r.type === "T");
    const hail = filtered.filter(r => r.type === "H");
    const wind = filtered.filter(r => r.type === "W");

    const fmt = (arr, label) => {
      if (!arr.length) return "";
      const items = arr.slice(0, 10).map(r => `  ${r.time ?? "?"} UTC — ${r.location ?? "?"}, ${r.st ?? "?"} (${r.size || r.mag || "?"}) — ${r.comments ?? ""}`.trim());
      return `\n${label} (${arr.length}):\n${items.join("\n")}`;
    };

    const stateLabel = state ? ` in ${state.toUpperCase()}` : "";
    return {
      content: [{
        type: "text",
        text: `SPC Storm Reports${stateLabel} — Today:\n${fmt(tornadoes, "Tornadoes")}${fmt(hail, "Large Hail")}${fmt(wind, "Damaging Wind")}\n\nSource: Storm Prediction Center`,
      }],
    };
  }
);

// ── Tool 7: Air quality ──────────────────────────────────────────────────────

server.tool(
  "get_air_quality",
  "Get current air quality index (AQI) for any US location — PM2.5, PM10, ozone levels and health categories. Great for wildfire smoke, pollution events, and ozone alerts.",
  {
    location: z.string().describe("City name or location, e.g. 'Los Angeles', 'Phoenix AZ', 'Denver Colorado'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const url = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&hourly=pm10,pm2_5,us_aqi,ozone&timezone=auto&forecast_days=1`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Air quality API error: ${res.status}`);
    const data = await res.json();

    const h = data.hourly;
    const now = new Date();
    const startIdx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));

    const currentAqi = h.us_aqi[startIdx];
    const category = AQI_CATS.find(c => currentAqi <= c.max) ?? AQI_CATS.at(-1);

    const lines = [
      `Air Quality — ${placeName}:`,
      `${category.emoji} US AQI: ${currentAqi} — ${category.label}`,
    ];
    if (h.pm2_5[startIdx] != null) lines.push(`PM2.5: ${h.pm2_5[startIdx].toFixed(1)} µg/m³`);
    if (h.pm10[startIdx] != null) lines.push(`PM10: ${h.pm10[startIdx].toFixed(1)} µg/m³`);
    if (h.ozone[startIdx] != null) lines.push(`Ozone: ${h.ozone[startIdx].toFixed(1)} µg/m³`);

    // 6-hour trend
    const trend = [];
    for (let i = startIdx; i < Math.min(startIdx + 6, h.time.length); i++) {
      const time = new Date(h.time[i]).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      const aqi = h.us_aqi[i];
      const cat = AQI_CATS.find(c => aqi <= c.max);
      trend.push(`  ${time}: AQI ${aqi ?? "?"} ${cat?.emoji ?? ""}`);
    }
    lines.push(`\nNext 6 hours:\n${trend.join("\n")}`);

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 8: Tropical weather / active hurricanes ─────────────────────────────

server.tool(
  "get_tropical_weather",
  "Get active tropical storm and hurricane information from the National Hurricane Center — current location, wind speed, pressure, and movement for all active Atlantic and Eastern Pacific storms",
  {},
  async () => {
    const res = await fetch("https://www.nhc.noaa.gov/CurrentStorms.json", { headers: NWS_HEADERS });
    if (!res.ok) throw new Error(`NHC API error: ${res.status}`);
    const data = await res.json();

    const storms = data.activeStorms ?? [];
    if (storms.length === 0) {
      return { content: [{ type: "text", text: "No active tropical cyclones in the Atlantic or Eastern Pacific at this time." }] };
    }

    const TYPES = {
      HU: "Hurricane", TS: "Tropical Storm", TD: "Tropical Depression",
      SD: "Subtropical Depression", SS: "Subtropical Storm",
      EX: "Extratropical Cyclone", DB: "Disturbance", LO: "Low",
    };
    const BASINS = { AT: "Atlantic", EP: "Eastern Pacific", CP: "Central Pacific" };

    const lines = [`Active Tropical Cyclones (${storms.length}):\n`];
    for (const s of storms) {
      const type = TYPES[s.classification] ?? s.classification ?? "System";
      const basin = BASINS[s.binNumber?.slice(0, 2)] ?? "Unknown basin";
      const winds = s.intensity ? `${s.intensity} mph` : "intensity unknown";
      const pressure = s.pressure ? `${s.pressure} mb` : "";
      const move = s.movementDir != null ? `moving ${dirToCardinal(s.movementDir)} at ${s.movementSpeed ?? "?"} mph` : "";
      lines.push(`${type} ${s.name} (${basin})`);
      lines.push(`  Position: ${s.latitude}, ${s.longitude}`);
      lines.push(`  Winds: ${winds}${pressure ? " | Pressure: " + pressure : ""}`);
      if (move) lines.push(`  Movement: ${move}`);
      if (s.lastUpdate) lines.push(`  Updated: ${new Date(s.lastUpdate).toLocaleString()}`);
      lines.push("");
    }
    lines.push("Source: National Hurricane Center (nhc.noaa.gov)");

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// Compute flight category from ceiling + visibility when fltCat is absent in API response.
// Handles both the old flat fields (cldCvg1/cldBas1) and the current clouds[] array format.
function computeFlightCategory(m) {
  const cloudSources = Array.isArray(m.clouds)
    ? m.clouds.map(c => ({ cov: c.cover, base: c.base }))
    : [
        { cov: m.cldCvg1, base: m.cldBas1 },
        { cov: m.cldCvg2, base: m.cldBas2 },
        { cov: m.cldCvg3, base: m.cldBas3 },
      ];
  const ceilLayers = cloudSources.filter(l => (l.cov === "BKN" || l.cov === "OVC") && l.base != null);
  const ceil = ceilLayers.length > 0 ? ceilLayers[0].base : Infinity;
  const vis = parseFloat(m.visib) || Infinity;   // handles "10+", "10", numbers
  if (ceil < 500  || vis < 1) return "LIFR";
  if (ceil < 1000 || vis < 3) return "IFR";
  if (ceil < 3000 || vis < 5) return "MVFR";
  return "VFR";
}

// ── Tool 9: Aviation weather (METAR + TAF) ───────────────────────────────────

server.tool(
  "get_aviation_weather",
  "Get current aviation weather for an airport — METAR observation, flight category (VFR/MVFR/IFR/LIFR), ceiling, visibility, winds, and TAF forecast. Uses 3-letter or 4-letter airport codes.",
  {
    airport: z.string().describe("Airport ICAO code (4 letters, e.g. KOKC) or IATA code (3 letters, e.g. OKC, DFW, LAX). US airports get 'K' prefix automatically."),
  },
  async ({ airport }) => {
    const upper = airport.trim().toUpperCase();
    const icao = upper.length === 3 ? `K${upper}` : upper;

    const [metarRes, tafRes] = await Promise.allSettled([
      fetch(`https://aviationweather.gov/api/data/metar?ids=${icao}&format=json&hours=2`).then(r => r.json()),
      fetch(`https://aviationweather.gov/api/data/taf?ids=${icao}&format=json`).then(r => r.json()),
    ]);

    const CAT_EMOJI = { VFR: "🟢", MVFR: "🔵", IFR: "🟡", LIFR: "🔴" };
    const sections = [`Aviation Weather — ${icao}:\n`];

    if (metarRes.status === "fulfilled" && Array.isArray(metarRes.value) && metarRes.value.length > 0) {
      const m = metarRes.value[0];
      // API returns fltCat (camelCase) — also accept fltcat for backward compatibility
      const flightCat = m.fltCat ?? m.fltcat ?? computeFlightCategory(m);
      sections.push(`${CAT_EMOJI[flightCat] ?? "⚪"} Flight Category: ${flightCat}`);
      if (m.obsTime) sections.push(`Observed: ${new Date(m.obsTime * 1000).toLocaleString()}`);
      if (m.temp != null) sections.push(`Temp/Dewpoint: ${m.temp}°C / ${m.dewp ?? "?"}°C (${Math.round(m.temp * 9/5 + 32)}°F)`);
      if (m.wspd != null) {
        const dir = m.wdir ?? "VRB";
        const gusts = m.wgst ? ` gusting ${m.wgst}kt` : "";
        sections.push(`Wind: ${dir}° at ${m.wspd}kt${gusts}`);
      }
      if (m.visib != null) sections.push(`Visibility: ${m.visib} SM`);
      // Ceiling = lowest BKN or OVC layer — handles both clouds[] array and flat cldCvg1/cldBas1 fields
      const cloudSrc = Array.isArray(m.clouds)
        ? m.clouds.map(c => ({ cov: c.cover, base: c.base }))
        : [{ cov: m.cldCvg1, base: m.cldBas1 }, { cov: m.cldCvg2, base: m.cldBas2 }, { cov: m.cldCvg3, base: m.cldBas3 }];
      const ceilLayers = cloudSrc.filter(l => (l.cov === "BKN" || l.cov === "OVC") && l.base != null);
      if (ceilLayers.length > 0) sections.push(`Ceiling: ${ceilLayers[0].base} ft AGL (${ceilLayers[0].cov})`);
      if (m.altim != null) sections.push(`Altimeter: ${(m.altim / 33.8639).toFixed(2)} inHg`);
      if (m.wxString) sections.push(`Weather: ${m.wxString}`);
      if (m.rawOb) sections.push(`\nRaw METAR: ${m.rawOb}`);
    } else {
      sections.push("METAR: No recent observation available for this station.");
    }

    if (tafRes.status === "fulfilled" && Array.isArray(tafRes.value) && tafRes.value.length > 0) {
      const t = tafRes.value[0];
      if (t.rawTAF) sections.push(`\nTAF:\n${t.rawTAF}`);
    } else {
      sections.push("\nTAF: Not available for this station.");
    }

    return { content: [{ type: "text", text: sections.join("\n") }] };
  }
);

// ── Tool 10: Historical weather lookup ───────────────────────────────────────

server.tool(
  "get_historical_weather",
  "Look up what the actual weather was on any past date for a location — daily high, low, precipitation, and conditions. Useful for anniversaries, event planning, storm research, or 'what was the weather last April 27?'",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Boston MA', 'Miami Florida'"),
    date: z.string().describe("Date in YYYY-MM-DD format, e.g. '2024-05-03' or '2023-04-27'. Must be a past date."),
  },
  async ({ location, date }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const url = `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}&start_date=${date}&end_date=${date}&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,windspeed_10m_max,weathercode&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Historical weather API error: ${res.status}`);
    const data = await res.json();

    const d = data.daily;
    if (!d?.time?.length) {
      return { content: [{ type: "text", text: `No historical data found for ${placeName} on ${date}.` }] };
    }

    const code = d.weathercode?.[0];
    const cond = WMO[code] ?? `Code ${code}`;
    const hi = d.temperature_2m_max?.[0];
    const lo = d.temperature_2m_min?.[0];
    const mean = d.temperature_2m_mean?.[0];
    const precip = d.precipitation_sum?.[0];
    const wind = d.windspeed_10m_max?.[0];

    const lines = [
      `Historical Weather — ${placeName} on ${date}:`,
      `High: ${hi != null ? Math.round(hi) + "°F" : "?"}`,
      `Low: ${lo != null ? Math.round(lo) + "°F" : "?"}`,
      `Mean: ${mean != null ? Math.round(mean) + "°F" : "?"}`,
      `Precipitation: ${precip != null ? precip.toFixed(2) + '"' : "?"}`,
      `Max Wind: ${wind != null ? Math.round(wind) + " mph" : "?"}`,
      `Conditions: ${cond}`,
    ];

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 11: Earthquake activity ─────────────────────────────────────────────

server.tool(
  "get_earthquake_activity",
  "Get recent earthquake activity near any location from the USGS — magnitude, depth, location, and timing. Useful for seismic awareness, post-quake queries, and Oklahoma injection-well induced seismicity.",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'San Francisco CA', 'Anchorage Alaska'"),
    radius_km: z.number().int().min(50).max(1000).default(300).describe("Search radius in kilometers (default 300)"),
    min_magnitude: z.number().min(0.5).max(8).default(2.5).describe("Minimum magnitude to include (default 2.5)"),
    days: z.number().int().min(1).max(30).default(7).describe("How many days back to search (default 7)"),
  },
  async ({ location, radius_km, min_magnitude, days }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const endTime = new Date().toISOString().split('.')[0] + "Z";
    const startTime = new Date(Date.now() - days * 86400000).toISOString().split('.')[0] + "Z";

    const url = `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=${startTime}&endtime=${endTime}&latitude=${lat}&longitude=${lon}&maxradiuskm=${radius_km}&minmagnitude=${min_magnitude}&orderby=magnitude&limit=20`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`USGS earthquake API error: ${res.status}`);
    const data = await res.json();

    const quakes = data.features ?? [];
    if (quakes.length === 0) {
      return { content: [{ type: "text", text: `No earthquakes M${min_magnitude}+ within ${radius_km} km of ${placeName} in the past ${days} day${days !== 1 ? "s" : ""}.` }] };
    }

    const lines = [`Earthquake Activity — ${radius_km}km radius of ${placeName} (past ${days} day${days !== 1 ? "s" : ""}):\n${quakes.length} event(s) M${min_magnitude}+\n`];

    for (const q of quakes.slice(0, 15)) {
      const p = q.properties;
      const coords = q.geometry?.coordinates;
      const dist = coords ? distKm(lat, lon, coords[1], coords[0]) : null;
      const time = new Date(p.time).toLocaleString();
      const depth = coords?.[2] != null ? `${coords[2].toFixed(0)} km deep` : "";
      const distStr = dist != null ? ` | ${dist.toFixed(0)} km away` : "";
      lines.push(`M${p.mag?.toFixed(1)} — ${p.place ?? "unknown"}`);
      lines.push(`  ${time}${distStr}${depth ? " | " + depth : ""}`);
    }

    lines.push("\nSource: USGS National Earthquake Information Center (usgs.gov)");
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Agent Tool 12: Full weather briefing (compound) ──────────────────────────

server.tool(
  "get_weather_briefing",
  "AGENT: Get a comprehensive weather briefing for any location — combines active alerts, SPC severe outlook, and 6-hour forecast into one unified threat summary. Use this when someone asks for a general weather overview or 'what's the weather situation' for a place.",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Dallas TX'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    let stateCode = null;
    try {
      const ptRes = await fetch(`https://api.weather.gov/points/${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
      if (ptRes.ok) {
        const pt = await ptRes.json();
        stateCode = pt.properties?.relativeLocation?.properties?.state ?? null;
      }
    } catch (_) {}

    const [alertsRes, spcRes, fcastRes] = await Promise.allSettled([
      stateCode
        ? fetch(`https://api.weather.gov/alerts/active?area=${stateCode}&status=actual`, { headers: NWS_HEADERS }).then(r => r.json())
        : Promise.resolve(null),
      fetch("https://www.spc.noaa.gov/products/outlook/day1otlk.txt").then(r => r.text()),
      fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=temperature_2m,precipitation,windspeed_10m,weathercode&forecast_days=1&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&models=best_match`).then(r => r.json()),
    ]);

    const sections = [`Weather Briefing — ${placeName}\n${"─".repeat(40)}`];

    if (alertsRes.status === "fulfilled" && alertsRes.value?.features?.length) {
      const alerts = alertsRes.value.features;
      const severe = alerts.filter(f => ["Extreme","Severe"].includes(f.properties?.severity));
      const others = alerts.filter(f => !["Extreme","Severe"].includes(f.properties?.severity));
      let alertText = `\nACTIVE ALERTS (${alerts.length} for ${stateCode}):`;
      severe.forEach(f => alertText += `\n[SEVERE] ${f.properties.event} — ${f.properties.areaDesc}`);
      others.slice(0, 3).forEach(f => alertText += `\n[WATCH/ADV] ${f.properties.event} — ${f.properties.areaDesc}`);
      if (others.length > 3) alertText += `\n   ...and ${others.length - 3} more`;
      sections.push(alertText);
    } else {
      sections.push(`\nNo active alerts for this area.`);
    }

    if (spcRes.status === "fulfilled") {
      const spcLines = spcRes.value.split("\n").map(l => l.trim()).filter(Boolean);
      const start = spcLines.findIndex(l => /THERE IS|SLIGHT|MARGINAL|ENHANCED|MODERATE|HIGH|NO SEVERE/.test(l));
      if (start >= 0) {
        const excerpt = spcLines.slice(start, start + 4).join(" ");
        sections.push(`\nSPC DAY 1 OUTLOOK:\n${excerpt}`);
      }
    }

    if (fcastRes.status === "fulfilled") {
      const h = fcastRes.value.hourly;
      const now = new Date();
      const startIdx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));
      const flines = [];
      for (let i = startIdx; i < Math.min(startIdx + 6, h.time.length); i++) {
        const time = new Date(h.time[i]).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        const temp = h.temperature_2m[i] != null ? `${Math.round(h.temperature_2m[i])}°F` : "?";
        const cond = WMO[h.weathercode[i]] ?? "Unknown";
        const wind = h.windspeed_10m[i] != null ? `${Math.round(h.windspeed_10m[i])} mph` : "?";
        const precip = h.precipitation[i] > 0 ? ` | ${h.precipitation[i].toFixed(2)}" precip` : "";
        flines.push(`  ${time}: ${temp}, ${cond}, Wind ${wind}${precip}`);
      }
      sections.push(`\nNEXT 6 HOURS:\n${flines.join("\n")}`);
    }

    return { content: [{ type: "text", text: sections.join("\n") }] };
  }
);

// ── Agent Tool 13: Regional river summary (compound) ─────────────────────────

server.tool(
  "get_river_summary",
  "AGENT: Get a regional flood picture for an area — finds multiple nearby NWS river gauges and summarizes which are elevated, at flood stage, or normal. Better than get_nearest_gauge when you want an overview of regional flooding.",
  {
    location: z.string().describe("City name or region, e.g. 'Tulsa OK', 'Mississippi Delta', 'St. Louis'"),
    radius_miles: z.number().int().min(10).max(150).default(60).describe("Search radius in miles (default 60)"),
  },
  async ({ location, radius_miles }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const url = `https://mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query?geometry=${lon},${lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&distance=${radius_miles}&units=esriSRUnit_StatuteMile&outFields=gaugelid,location,observed,status,units,waterbody,state,obstime&returnGeometry=true&f=json`;
    const res = await fetch(url, { headers: NWS_HEADERS });
    if (!res.ok) throw new Error(`Gauge MapServer error: ${res.status}`);
    const data = await res.json();

    const features = data.features ?? [];
    if (features.length === 0) {
      return { content: [{ type: "text", text: `No river gauges found within ${radius_miles} miles of ${placeName}.` }] };
    }

    const withDist = features
      .filter(f => f.geometry?.x != null)
      .map(f => ({ ...f, dist: distKm(lat, lon, f.geometry.y, f.geometry.x) }))
      .sort((a, b) => a.dist - b.dist);

    const STATUS_ORDER = ["major", "moderate", "minor", "action", "no_flooding", "unknown"];
    const STATUS_EMOJI = { major: "MAJOR FLOOD", moderate: "MODERATE FLOOD", minor: "MINOR FLOOD", action: "ACTION STAGE", no_flooding: "Normal", unknown: "Unknown" };

    const byStatus = {};
    for (const f of withDist) {
      const s = (f.attributes.status ?? "unknown").toLowerCase().replace(" ", "_");
      const key = STATUS_ORDER.find(k => s.includes(k)) ?? "unknown";
      if (!byStatus[key]) byStatus[key] = [];
      byStatus[key].push(f);
    }

    const lines = [`River Gauge Summary — ${radius_miles}-mile radius of ${placeName} (${withDist.length} gauges):\n`];
    for (const key of STATUS_ORDER) {
      const group = byStatus[key];
      if (!group?.length) continue;
      const label = STATUS_EMOJI[key];
      lines.push(`[${label}] (${group.length}):`);
      group.slice(0, 5).forEach(f => {
        const a = f.attributes;
        lines.push(`  ${a.location ?? a.gaugelid} — ${a.waterbody ?? "?"} — ${a.observed ?? "?"} ${a.units ?? "ft"} (${f.dist.toFixed(0)} km away)`);
      });
      if (group.length > 5) lines.push(`  ...and ${group.length - 5} more`);
    }

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Agent Tool 14: All-hazards briefing (compound) ───────────────────────────

server.tool(
  "get_all_hazards_briefing",
  "AGENT: The most comprehensive StormWatch briefing — combines NWS alerts, SPC severe outlook, fire weather, active tropical storms, air quality, and nearby flood gauges into one complete all-hazards picture. Use this for a full situational awareness report on any location.",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Dallas TX', 'Tampa Florida'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    let stateCode = null;
    try {
      const ptRes = await fetch(`https://api.weather.gov/points/${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
      if (ptRes.ok) {
        const pt = await ptRes.json();
        stateCode = pt.properties?.relativeLocation?.properties?.state ?? null;
      }
    } catch (_) {}

    const [alertsRes, spcSevereRes, spcFireRes, tropicalRes, aqiRes, floodRes, fcastRes] = await Promise.allSettled([
      stateCode
        ? fetch(`https://api.weather.gov/alerts/active?area=${stateCode}&status=actual`, { headers: NWS_HEADERS }).then(r => r.json())
        : Promise.resolve(null),
      fetch("https://www.spc.noaa.gov/products/outlook/day1otlk.txt").then(r => r.text()),
      fetch("https://www.spc.noaa.gov/products/fire_weather/fwdy1.txt").then(r => r.ok ? r.text() : null),
      fetch("https://www.nhc.noaa.gov/CurrentStorms.json", { headers: NWS_HEADERS }).then(r => r.json()),
      fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&hourly=us_aqi&timezone=auto&forecast_days=1`).then(r => r.json()),
      fetch(`https://mapservices.weather.noaa.gov/eventdriven/rest/services/water/riv_gauges/MapServer/0/query?geometry=${lon},${lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&distance=50&units=esriSRUnit_StatuteMile&outFields=gaugelid,location,observed,status,units,waterbody&returnGeometry=false&f=json`, { headers: NWS_HEADERS }).then(r => r.json()),
      fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=temperature_2m,precipitation,windspeed_10m,weathercode&forecast_days=1&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&models=best_match`).then(r => r.json()),
    ]);

    const sections = [
      `ALL-HAZARDS BRIEFING — ${placeName}`,
      `Generated: ${new Date().toLocaleString()}`,
      "═".repeat(44),
    ];

    // CURRENT CONDITIONS (forecast first hour)
    if (fcastRes.status === "fulfilled") {
      const h = fcastRes.value.hourly;
      const now = new Date();
      const idx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));
      const temp = h.temperature_2m[idx] != null ? `${Math.round(h.temperature_2m[idx])}°F` : "?";
      const wind = h.windspeed_10m[idx] != null ? `${Math.round(h.windspeed_10m[idx])} mph` : "?";
      const cond = WMO[h.weathercode[idx]] ?? "Unknown";
      sections.push(`\nCURRENT CONDITIONS: ${temp}, ${cond}, Wind ${wind}`);
    }

    // NWS ALERTS
    if (alertsRes.status === "fulfilled" && alertsRes.value?.features?.length) {
      const alerts = alertsRes.value.features;
      const extreme = alerts.filter(f => f.properties?.severity === "Extreme");
      const severe = alerts.filter(f => f.properties?.severity === "Severe");
      const other = alerts.filter(f => !["Extreme","Severe"].includes(f.properties?.severity));
      let txt = `\nACTIVE ALERTS — ${stateCode} (${alerts.length} total):`;
      extreme.forEach(f => txt += `\n[EXTREME] ${f.properties.event} — ${f.properties.areaDesc?.split(";")[0]}`);
      severe.forEach(f => txt += `\n[SEVERE] ${f.properties.event} — ${f.properties.areaDesc?.split(";")[0]}`);
      other.slice(0, 4).forEach(f => txt += `\n[WATCH/ADV] ${f.properties.event}`);
      if (other.length > 4) txt += `\n  (+${other.length - 4} more)`;
      sections.push(txt);
    } else {
      sections.push(`\nALERTS: No active NWS alerts for ${stateCode ?? "this area"}.`);
    }

    // SPC SEVERE
    if (spcSevereRes.status === "fulfilled") {
      const lines = spcSevereRes.value.split("\n").map(l => l.trim()).filter(Boolean);
      const s = lines.findIndex(l => /THERE IS|SLIGHT|MARGINAL|ENHANCED|MODERATE|HIGH|NO SEVERE/.test(l));
      if (s >= 0) {
        const excerpt = lines.slice(s, s + 3).join(" ").slice(0, 300);
        sections.push(`\nSPC SEVERE OUTLOOK:\n${excerpt}`);
      }
    }

    // SPC FIRE WEATHER
    if (spcFireRes.status === "fulfilled" && spcFireRes.value) {
      const lines = spcFireRes.value.split("\n").map(l => l.trim()).filter(Boolean);
      const s = lines.findIndex(l => /FIRE WEATHER|ELEVATED|CRITICAL|NO CRITICAL|THERE IS/.test(l));
      if (s >= 0) {
        const excerpt = lines.slice(s, s + 2).join(" ").slice(0, 200);
        sections.push(`\nFIRE WEATHER: ${excerpt}`);
      }
    } else {
      sections.push(`\nFIRE WEATHER: Outlook not available (check spc.noaa.gov).`);
    }

    // TROPICAL
    if (tropicalRes.status === "fulfilled") {
      const storms = tropicalRes.value.activeStorms ?? [];
      if (storms.length > 0) {
        const list = storms.map(s => `${s.classification} ${s.name} (${s.intensity ?? "?"} mph, ${s.latitude}, ${s.longitude})`).join(" | ");
        sections.push(`\nTROPICAL: ${storms.length} active system(s): ${list}`);
      } else {
        sections.push(`\nTROPICAL: No active tropical cyclones.`);
      }
    }

    // AIR QUALITY
    if (aqiRes.status === "fulfilled") {
      const h = aqiRes.value.hourly;
      const now = new Date();
      const idx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));
      const aqi = h.us_aqi[idx];
      const cat = AQI_CATS.find(c => aqi <= c.max) ?? AQI_CATS.at(-1);
      sections.push(`\nAIR QUALITY: AQI ${aqi} — ${cat.emoji} ${cat.label}`);
    }

    // FLOODING
    if (floodRes.status === "fulfilled") {
      const features = floodRes.value.features ?? [];
      const elevated = features.filter(f => {
        const s = (f.attributes.status ?? "").toLowerCase();
        return s.includes("minor") || s.includes("moderate") || s.includes("major");
      });
      if (elevated.length > 0) {
        sections.push(`\nFLOODING: ${elevated.length} gauge(s) at or above flood stage within 50 miles:`);
        elevated.slice(0, 4).forEach(f => {
          sections.push(`  ${f.attributes.location} — ${f.attributes.status} (${f.attributes.observed} ${f.attributes.units ?? "ft"})`);
        });
      } else {
        sections.push(`\nFLOODING: No significant flooding on nearby rivers.`);
      }
    }

    sections.push(`\n${"─".repeat(44)}\nSource: NWS, SPC, NHC, USGS, Open-Meteo`);

    return { content: [{ type: "text", text: sections.join("\n") }] };
  }
);

// ── WindNinja shared helpers ─────────────────────────────────────────────────

function parseWindNinjaOutput(text) {
  const ncols  = parseInt(text.match(/"ncols"\s*:\s*(\d+)/)?.[1] ?? "0");
  const nrows  = parseInt(text.match(/"nrows"\s*:\s*(\d+)/)?.[1] ?? "0");
  const xll    = parseFloat(text.match(/"xllcorner"\s*:\s*([-\d.]+)/)?.[1] ?? "0");
  const yll    = parseFloat(text.match(/"yllcorner"\s*:\s*([-\d.]+)/)?.[1] ?? "0");
  const cell   = parseFloat(text.match(/"cellsize"\s*:\s*([-\d.]+)/)?.[1] ?? "0");
  const nodata = parseFloat(text.match(/"NODATA_value"\s*:\s*([-\d.]+)/)?.[1] ?? "-9999");
  const section = text.match(/"data"\s*:\s*\[([\s\S]*?)\]/)?.[1] ?? "";
  const data = section.split(/[\s,]+/).filter(s => s.length > 0).map(Number)
    .filter(v => !isNaN(v) && v !== nodata && v >= 0);
  return { ncols, nrows, xll, yll, cell, data };
}

// Runs WindNinja and returns parsed vel + ang grids. Cleans up output files; keeps DEM cached.
async function runWindNinjaCore(lat, lon, windSpeed, windDir, radiusMiles, vegetation) {
  if (!existsSync(WINDNINJA_CACHE)) mkdirSync(WINDNINJA_CACHE, { recursive: true });

  const latKey = (Math.round(lat * 10) / 10).toFixed(1);
  const lonKey = (Math.round(lon * 10) / 10).toFixed(1);
  const demPath = `${WINDNINJA_CACHE}\\dem_${latKey}_${lonKey}_${radiusMiles}mi.tif`;
  const demCached = existsSync(demPath);

  const args = ["--num_threads", "8"];
  if (demCached) {
    args.push("--elevation_file", demPath);
  } else {
    args.push(
      "--fetch_elevation", demPath,
      "--x_center", String(lon), "--y_center", String(lat),
      "--x_buffer", String(radiusMiles), "--y_buffer", String(radiusMiles),
      "--buffer_units", "miles", "--elevation_source", "srtm",
    );
  }
  args.push(
    "--initialization_method", "domainAverageInitialization",
    "--input_speed", String(windSpeed), "--input_speed_units", "mph",
    "--input_direction", String(windDir),
    "--input_wind_height", "10", "--units_input_wind_height", "m",
    "--uni_air_temp", "70", "--air_temp_units", "F",
    "--uni_cloud_cover", "0.5", "--cloud_cover_units", "fraction",
    "--vegetation", vegetation, "--mesh_choice", "coarse",
    "--output_wind_height", "10", "--units_output_wind_height", "m",
    "--output_speed_units", "mph", "--output_path", WINDNINJA_CACHE,
    "--write_ascii_output", "true", "--ascii_out_json", "1", "--ascii_out_4326", "1",
  );

  let result;
  try {
    result = await execFileAsync(WINDNINJA_CLI, args, { timeout: 120000 });
  } catch (err) {
    throw new Error(`WindNinja simulation failed: ${err.stderr ?? err.message}`);
  }
  const combined = (result.stdout ?? "") + "\n" + (result.stderr ?? "");

  const velMatch = combined.match(/writing JSON output: (.+?_vel-4326\.json)/);
  const angMatch = combined.match(/writing JSON output: (.+?_ang-4326\.json)/);
  if (!velMatch) throw new Error("WindNinja completed but no velocity output file was reported.");

  const velPath = velMatch[1].trim();
  const angPath = angMatch?.[1]?.trim();

  const vel = parseWindNinjaOutput(readFileSync(velPath, "utf8"));
  let angData = null;
  if (angPath) {
    try { angData = parseWindNinjaOutput(readFileSync(angPath, "utf8")).data; } catch (_) {}
  }

  [velPath, angPath,
   velPath.replace("_vel-4326.json", "_cld-4326.json"),
   velPath.replace("_vel-4326.json", "_vel.json"),
   velPath.replace("_vel-4326.json", "_ang.json"),
   velPath.replace("_vel-4326.json", "_cld.json"),
  ].filter(Boolean).forEach(p => { try { unlinkSync(p); } catch (_) {} });

  return { vel, angData, combined, demCached };
}

// ── Tool 15: WindNinja terrain wind simulation ───────────────────────────────

server.tool(
  "get_terrain_wind",
  "Run a WindNinja terrain wind simulation — shows how local terrain modifies wind speed compared to open-air conditions. Identifies terrain-accelerated and sheltered zones. Critical for fire behavior, aviation, and mountain weather planning. Uses SRTM elevation data and runs in under 1 second for most areas.",
  {
    location: z.string().describe("City, peak, or place name, e.g. 'Tahlequah Oklahoma', 'Wichita Mountains', 'Glenwood Springs CO'"),
    wind_speed: z.number().min(1).max(100).describe("Input wind speed in mph — use get_point_forecast to get the current forecast wind for this location"),
    wind_direction: z.number().min(0).max(360).describe("Wind direction in degrees the wind is coming FROM (0=N, 90=E, 180=S, 270=W, 225=SW)"),
    radius_miles: z.number().min(1).max(15).default(5).describe("Domain radius in miles (default 5). Larger = more terrain context, slightly slower first run while DEM downloads."),
    vegetation: z.enum(["grass", "brush", "trees"]).default("grass").describe("Dominant ground cover — affects surface roughness in the simulation"),
  },
  async ({ location, wind_speed, wind_direction, radius_miles, vegetation }) => {
    const { lat, lon, name: placeName } = await geocode(location);
    const { vel, angData, combined, demCached } = await runWindNinjaCore(lat, lon, wind_speed, wind_direction, radius_miles, vegetation);

    if (!vel.data.length) throw new Error("Wind speed output file was empty or could not be parsed.");

    const speeds = vel.data;
    let min = Infinity, max = -Infinity;
    for (const v of speeds) { if (v < min) min = v; if (v > max) max = v; }
    const mean = speeds.reduce((a, b) => a + b, 0) / speeds.length;
    const sorted = [...speeds].sort((a, b) => a - b);
    const p10  = sorted[Math.floor(sorted.length * 0.10)];
    const p90  = sorted[Math.floor(sorted.length * 0.90)];
    const accel = max / wind_speed;

    const simTimeMatch = combined.match(/Total simulation time was ([\d.]+) seconds/);
    const simTime = simTimeMatch ? `${parseFloat(simTimeMatch[1]).toFixed(2)}s` : "?";

    const terrainLabel =
      accel > 1.5  ? "STRONG — major terrain amplification" :
      accel > 1.25 ? "MODERATE — notable local acceleration" :
      accel > 1.1  ? "MILD — slight terrain influence" :
                     "MINIMAL — relatively flat, little modification";

    const dirLabel = (d) => ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][Math.round(d / 22.5) % 16];

    const lines = [
      `Terrain Wind Analysis — ${placeName}`,
      `Domain: ${radius_miles * 2}-mile area | Grid: ${vel.ncols}×${vel.nrows} cells | Vegetation: ${vegetation} | Sim: ${simTime}${demCached ? " (DEM cached)" : " (DEM downloaded)"}`,
      ``,
      `INPUT WIND: ${wind_speed} mph from the ${dirLabel(wind_direction)} (${wind_direction}°)`,
      ``,
      `TERRAIN-MODIFIED RESULTS:`,
      `  Sheltered zones (P10): ${p10.toFixed(1)} mph`,
      `  Domain average:        ${mean.toFixed(1)} mph`,
      `  Exposed zones (P90):   ${p90.toFixed(1)} mph`,
      `  Peak speed (max):      ${max.toFixed(1)} mph  [+${((accel - 1) * 100).toFixed(0)}% above input]`,
      `  Speed spread:          ${(max - min).toFixed(1)} mph across the domain`,
      ``,
      `TERRAIN INFLUENCE: ${terrainLabel}`,
    ];

    if (accel > 1.3) {
      lines.push(``, `WARNING: Terrain is accelerating wind by ${((accel - 1) * 100).toFixed(0)}%. Peak terrain-driven winds of ${max.toFixed(0)} mph vs. ${wind_speed} mph open-air. This is significant for fire behavior and aviation planning.`);
    } else if (p10 < wind_speed * 0.7) {
      lines.push(``, `NOTE: Sheltered terrain areas drop to ${p10.toFixed(0)} mph — significant wind shadow effect in protected valleys or ridgelines.`);
    }

    lines.push(``, `Source: WindNinja 3.12.2 (USFS Fire Lab) + SRTM elevation`);

    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 16: Fire weather environment (fuel drought context) ─────────────────

server.tool(
  "get_fire_weather_environment",
  "Get the fuel drought context for any US location — 90-day precipitation deficit, consecutive dry days, surface soil moisture, current relative humidity, and fire environment severity rating. Use alongside get_fire_weather_outlook and get_terrain_wind for complete fire weather situational awareness. Answers 'how primed are the fuels right now?' — the question the Camp Fire report identified as critical.",
  {
    location: z.string().describe("City or location name, e.g. 'Paradise CA', 'Flagstaff Arizona', 'Bend Oregon'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const yesterday = new Date(Date.now() - 86400000).toISOString().split("T")[0];
    const d90ago   = new Date(Date.now() - 90 * 86400000).toISOString().split("T")[0];

    const [archiveRes, currentRes] = await Promise.allSettled([
      fetch(
        `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}` +
        `&start_date=${d90ago}&end_date=${yesterday}` +
        `&daily=precipitation_sum,temperature_2m_max,et0_fao_evapotranspiration` +
        `&precipitation_unit=inch&temperature_unit=fahrenheit&timezone=auto`
      ).then(r => r.json()),
      fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
        `&hourly=relative_humidity_2m,soil_moisture_0_to_1cm,windspeed_10m,temperature_2m` +
        `&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1`
      ).then(r => r.json()),
    ]);

    const lines = [
      `Fire Weather Environment — ${placeName}`,
      "─".repeat(42),
    ];

    // ── Current conditions (first available hour) ──
    if (currentRes.status === "fulfilled") {
      const h = currentRes.value.hourly;
      const now = new Date();
      const idx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));
      const rh      = h.relative_humidity_2m?.[idx];
      const sm      = h["soil_moisture_0_to_1cm"]?.[idx];
      const wind    = h.windspeed_10m?.[idx];
      const temp    = h.temperature_2m?.[idx];

      const rhLine  = rh   != null ? `RH: ${rh}%` : null;
      const smLine  = sm   != null ? `Surface soil moisture: ${(sm * 100).toFixed(1)}% volumetric` : null;
      const wLine   = wind != null ? `Wind: ${Math.round(wind)} mph` : null;
      const tLine   = temp != null ? `Temp: ${Math.round(temp)}°F` : null;
      lines.push(`\nCURRENT CONDITIONS: ${[tLine, rhLine, wLine].filter(Boolean).join(" | ")}`);
      if (smLine) lines.push(`  ${smLine}`);
    }

    // ── 90-day precipitation analysis ──
    if (archiveRes.status === "fulfilled") {
      const d = archiveRes.value.daily;
      const precip = (d?.precipitation_sum ?? []).filter(v => v != null);
      const maxTemps = (d?.temperature_2m_max ?? []).filter(v => v != null);
      const et0     = (d?.et0_fao_evapotranspiration ?? []).filter(v => v != null);

      if (precip.length > 0) {
        const total90   = precip.reduce((a, b) => a + b, 0);
        const total30   = precip.slice(-30).reduce((a, b) => a + b, 0);
        const dryDays   = precip.filter(v => v < 0.01).length;
        const rev       = [...precip].reverse();
        const sinceRain = rev.findIndex(v => v >= 0.10);
        const daysLabel = sinceRain === -1 ? "90+" : sinceRain === 0 ? "today" : String(sinceRain);
        const avgMaxT   = maxTemps.length ? maxTemps.reduce((a, b) => a + b, 0) / maxTemps.length : null;
        const totalET0  = et0.length ? et0.reduce((a, b) => a + b, 0) : null;
        const deficit   = totalET0 != null ? (totalET0 - total90).toFixed(1) : null;

        lines.push(`\nPRECIPITATION — past 90 days (through ${yesterday}):`);
        lines.push(`  Total:              ${total90.toFixed(2)}"`);
        lines.push(`  Last 30 days:       ${total30.toFixed(2)}"`);
        lines.push(`  Dry days (<0.01"):  ${dryDays} of ${precip.length}`);
        lines.push(`  Since 0.10" rain:   ${daysLabel} day${daysLabel !== "today" && daysLabel !== "90+" ? "s" : ""}`);
        if (avgMaxT != null) lines.push(`  Avg high temp:      ${avgMaxT.toFixed(0)}°F`);
        if (deficit != null) lines.push(`  Moisture deficit:   ${deficit}" (ET minus precip)`);

        // ── Severity rating — primary driver is 90-day precip; dry days secondary ──
        let severity = "NORMAL";
        const reasons = [];

        // Precipitation total (primary)
        if      (total90 < 0.5)  { severity = "EXTREME";  reasons.push(`only ${total90.toFixed(2)}" in 90 days`); }
        else if (total90 < 2.0)  { severity = "HIGH";     reasons.push(`only ${total90.toFixed(2)}" in 90 days`); }
        else if (total90 < 5.0)  { severity = "ELEVATED"; reasons.push(`${total90.toFixed(2)}" in 90 days`); }

        // Dry days — only meaningful when total precip is also low
        if (dryDays >= 75 && total90 < 5.0 && severity !== "EXTREME") {
          if (severity !== "HIGH") severity = "HIGH";
          reasons.push(`${dryDays} dry days`);
        } else if (dryDays >= 50 && total90 < 3.0 && severity === "NORMAL") {
          severity = "ELEVATED"; reasons.push(`${dryDays} dry days`);
        }

        // Days since last meaningful rain
        if (sinceRain >= 60 && total90 < 3.0) {
          if (severity === "NORMAL" || severity === "ELEVATED") severity = "HIGH";
          reasons.push(`${sinceRain} days without 0.10" rain`);
        } else if (sinceRain >= 30 && total90 < 5.0 && severity === "NORMAL") {
          severity = "ELEVATED"; reasons.push(`${sinceRain} days without meaningful rain`);
        }

        // Moisture deficit — upgrade if ET strongly outpacing precip
        if (deficit != null) {
          const defNum = parseFloat(deficit);
          if (defNum > 10 && severity !== "EXTREME") {
            if (severity === "NORMAL" || severity === "ELEVATED") severity = "HIGH";
            reasons.push(`${defNum.toFixed(1)}" moisture deficit (ET exceeds precip)`);
          }
        }

        // RH — always flag; can push to EXTREME
        const rh = currentRes.status === "fulfilled"
          ? currentRes.value.hourly?.relative_humidity_2m?.[Math.max(0, currentRes.value.hourly.time.findIndex(t => new Date(t) >= new Date()))]
          : null;
        if (rh != null && rh < 15) {
          severity = "EXTREME"; reasons.push(`RH ${rh}% (critical fire weather threshold)`);
        } else if (rh != null && rh < 25) {
          if (severity === "NORMAL") severity = "ELEVATED";
          reasons.push(`RH ${rh}% (below fire weather threshold)`);
        }

        const SEVERITY_DESC = {
          EXTREME:  "EXTREME — fuel moisture conditions approaching historic lows. ERC likely at or above 90th percentile. Fire ignition easy, growth explosive.",
          HIGH:     "HIGH — well-dried fuels with significant moisture deficit. Active fire weather day if wind/RH align. ERC elevated.",
          ELEVATED: "ELEVATED — fuels drying below seasonal normal. Monitor wind and RH trends.",
          NORMAL:   "NORMAL — fuel moisture appears near seasonal average.",
        };

        lines.push(`\nFIRE ENVIRONMENT: ${severity}`);
        lines.push(`  ${SEVERITY_DESC[severity]}`);
        if (reasons.length) lines.push(`  Factors: ${reasons.join(" | ")}`);

        // ── Camp Fire comparison flag ──
        if (dryDays >= 60 && severity === "EXTREME") {
          lines.push(`\n⚠  CAMP FIRE ANALOG: ${dryDays} dry days and severe precip deficit are consistent with`);
          lines.push(`   the November 8, 2018 Camp Fire environment — 200+ dry days, ERC at 99th percentile`);
          lines.push(`   for November, fuels burning like August. Pair with get_terrain_wind for full picture.`);
        }
      }
    } else {
      lines.push(`\nPrecipitation data unavailable: ${archiveRes.reason}`);
    }

    lines.push(`\nSource: Open-Meteo Forecast & Archive APIs`);
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 17: NOAA US Drought Monitor conditions ──────────────────────────────

server.tool(
  "get_drought_conditions",
  "Get current drought conditions for any US location from the NOAA US Drought Monitor — county-level and state-level D0–D4 drought severity with area percentages. Updated weekly every Tuesday. Use alongside get_fire_weather_environment for complete fuel drought context.",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Phoenix AZ', 'Dallas Texas'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    // FCC census block geocoder → county FIPS, county name, state abbreviation + FIPS
    let countyFips = null, countyName = null, stateCode = null, stateFips = null;
    try {
      const fcc = await fetch(`https://geo.fcc.gov/api/census/block/find?latitude=${lat}&longitude=${lon}&format=json`).then(r => r.json());
      countyFips = fcc.County?.FIPS;
      countyName = fcc.County?.name;
      stateCode  = fcc.State?.code;   // "OK"
      stateFips  = fcc.State?.FIPS;   // "40" — required by USDM state endpoint
    } catch (_) {}

    // USDM publishes new data each Tuesday; use a 14-day window to catch the latest release
    const endDate = new Date();
    const startDate = new Date(Date.now() - 14 * 86400000);
    const fmt = d => d.toISOString().split("T")[0];

    const CATS = [
      { key: "D4", label: "D4 Exceptional",    emoji: "⚫" },
      { key: "D3", label: "D3 Extreme",        emoji: "🔴" },
      { key: "D2", label: "D2 Severe",         emoji: "🟠" },
      { key: "D1", label: "D1 Moderate",       emoji: "🟡" },
      { key: "D0", label: "D0 Abnormally Dry", emoji: "🟢" },
    ];

    // USDM returns CSV (not JSON); values are area in sq miles — compute percentages from totals
    const fetchUsdm = async (level, aoi) => {
      const url = `https://usdmdataservices.unl.edu/api/${level}Statistics/GetDroughtSeverityStatisticsByArea?aoi=${aoi}&startdate=${fmt(startDate)}&enddate=${fmt(endDate)}&statisticsType=2`;
      const res = await fetch(url);
      if (!res.ok) return null;
      const text = await res.text();
      const lines = text.trim().split("\n").filter(Boolean);
      if (lines.length < 2) return null;
      // CSV parser that handles quoted values containing commas (e.g. "13,851.40")
      const parseRow = line => {
        const cols = []; let cur = '', inQ = false;
        for (const ch of line) {
          if (ch === '"') { inQ = !inQ; }
          else if (ch === ',' && !inQ) { cols.push(cur); cur = ''; }
          else { cur += ch; }
        }
        cols.push(cur);
        return cols.map(c => c.replace(/,/g, '').trim());
      };
      const headers = parseRow(lines[0]);
      const lastRow = parseRow(lines[lines.length - 1]);
      const obj = {};
      headers.forEach((h, i) => obj[h] = lastRow[i] ?? '');
      // Convert sq-mile areas to percentages
      const total = ['None','D0','D1','D2','D3','D4'].reduce((s, k) => s + (parseFloat(obj[k]) || 0), 0);
      if (total > 0) ['None','D0','D1','D2','D3','D4'].forEach(k => { obj[k] = ((parseFloat(obj[k]) || 0) / total * 100).toFixed(1); });
      return obj;
    };

    const lines = [`Drought Conditions — ${placeName}\n${"─".repeat(40)}`];

    // County-level breakdown
    if (countyFips && countyName) {
      try {
        const row = await fetchUsdm("County", countyFips);
        if (row) {
          const md = row.MapDate ?? '';
          const mapDate = md.length === 8 ? `${md.slice(0,4)}-${md.slice(4,6)}-${md.slice(6,8)}` : "current";
          lines.push(`\n${countyName} County, ${stateCode ?? ""} (week ending ${mapDate}):`);
          const none = parseFloat(row.None ?? 0);
          if (none > 0) lines.push(`  No drought:        ${none.toFixed(1)}%`);
          for (const { key, label, emoji } of CATS) {
            const pct = parseFloat(row[key] ?? 0);
            if (pct > 0) lines.push(`  ${emoji} ${label}: ${pct.toFixed(1)}%`);
          }
          const worst = CATS.find(c => parseFloat(row[c.key] ?? 0) > 0);
          lines.push(worst
            ? `  → Worst category: ${worst.label}`
            : `  → No drought conditions in this county.`);
        }
      } catch (_) {}
    }

    // State-level context — USDM state endpoint requires numeric FIPS, not abbreviation
    if (stateFips) {
      try {
        const row = await fetchUsdm("State", stateFips);
        if (row) {
          lines.push(`\n${stateCode ?? stateFips} statewide:`);
          const none = parseFloat(row.None ?? 0);
          if (none > 0) lines.push(`  No drought: ${none.toFixed(1)}%`);
          for (const { key, label, emoji } of CATS) {
            const pct = parseFloat(row[key] ?? 0);
            if (pct > 0) lines.push(`  ${emoji} ${label}: ${pct.toFixed(1)}%`);
          }
        }
      } catch (_) {}
    }

    if (lines.length === 2) {
      lines.push(`\nUnable to retrieve drought data — USDM API may be temporarily unavailable.`);
      lines.push(`Check https://droughtmonitor.unl.edu for current conditions.`);
    }

    lines.push(`\nSource: US Drought Monitor (droughtmonitor.unl.edu) — updated weekly (Tuesdays)`);
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 18: Extended seasonal outlook ──────────────────────────────────────

server.tool(
  "get_seasonal_outlook",
  "Get an extended seasonal outlook for any location — 16-day forecast summarized week by week, plus the NOAA Climate Prediction Center (CPC) 30-day outlook narrative when available. Answers 'what does the next few weeks look like for temperature and precipitation?'",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Minneapolis MN', 'Seattle Washington'"),
  },
  async ({ location }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    // Open-Meteo 16-day daily forecast (CPC text products are not available as plain-text endpoints)
    const [forecastRes] = await Promise.allSettled([
      fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
        `&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weathercode` +
        `&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=auto&forecast_days=16&models=best_match`
      ).then(r => r.json()),
    ]);

    const lines = [`Seasonal Outlook — ${placeName}\n${"─".repeat(40)}`];

    // 16-day forecast grouped into weekly summaries
    if (forecastRes.status === "fulfilled") {
      const d = forecastRes.value.daily;
      const weeklabels = ["Week 1 (days 1–7)", "Week 2 (days 8–14)"];

      for (let week = 0; week < 2; week++) {
        const s = week * 7;
        const e = Math.min(s + 7, d.time.length);
        if (s >= d.time.length) break;

        const dates = d.time.slice(s, e);
        const highs  = d.temperature_2m_max.slice(s, e).filter(v => v != null);
        const lows   = d.temperature_2m_min.slice(s, e).filter(v => v != null);
        const precip = d.precipitation_sum.slice(s, e).filter(v => v != null);
        const pop    = d.precipitation_probability_max.slice(s, e).filter(v => v != null);

        const avgHigh    = highs.length  ? Math.round(highs.reduce((a, b) => a + b, 0) / highs.length)  : null;
        const avgLow     = lows.length   ? Math.round(lows.reduce((a, b) => a + b, 0) / lows.length)    : null;
        const totalPrecip = precip.reduce((a, b) => a + b, 0);
        const maxPop     = pop.length    ? Math.max(...pop) : null;
        const maxHigh    = highs.length  ? Math.round(Math.max(...highs)) : null;
        const minLow     = lows.length   ? Math.round(Math.min(...lows))  : null;

        const tempChar   = avgHigh == null ? "?" : avgHigh > 90 ? "hot" : avgHigh > 75 ? "warm" : avgHigh > 55 ? "mild" : avgHigh > 40 ? "cool" : "cold";
        const precipChar = totalPrecip > 2 ? "wet" : totalPrecip > 0.5 ? "some rain" : "dry";

        lines.push(`\n${weeklabels[week]} (${dates[0]} → ${dates[dates.length - 1]}):`);
        if (avgHigh != null) lines.push(`  Avg high: ${avgHigh}°F  |  Avg low: ${avgLow}°F`);
        if (maxHigh != null) lines.push(`  Range: ${minLow}°F – ${maxHigh}°F`);
        lines.push(`  Total precip: ${totalPrecip.toFixed(2)}"  |  Max rain chance: ${maxPop ?? "?"}%`);
        lines.push(`  → ${tempChar.charAt(0).toUpperCase() + tempChar.slice(1)}, ${precipChar}`);
      }
    }

    lines.push(`\nCPC outlooks (maps — open in browser):`);
    lines.push(`  30-day: https://www.cpc.ncep.noaa.gov/products/predictions/30day/`);
    lines.push(`  3-month: https://www.cpc.ncep.noaa.gov/products/predictions/90day/`);

    lines.push(`\nSource: Open-Meteo 16-day forecast | NOAA Climate Prediction Center`);
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ── Tool 19: Multi-model forecast comparison ─────────────────────────────────

server.tool(
  "compare_model_forecasts",
  "Compare the GFS (American), ECMWF IFS (European), UKMO (UK Met Office), GEM (Canadian), and ICON (German) forecast models for any location — shows daily high/low temperature and precipitation from each model and flags where they agree or disagree. High spread = low forecast confidence. Low spread = high confidence.",
  {
    location: z.string().describe("City name or location, e.g. 'Oklahoma City', 'Denver CO', 'Boston Massachusetts'"),
    days: z.number().int().min(1).max(7).default(5).describe("Number of days to compare (1–7, default 5)"),
  },
  async ({ location, days }) => {
    const { lat, lon, name: placeName } = await geocode(location);

    const MODELS = [
      { id: "gfs_seamless",  name: "GFS (American)"  },
      { id: "ecmwf_ifs025", name: "ECMWF IFS (Euro)" },
      { id: "ukmo_seamless", name: "UKMO (UK Met)"   },
      { id: "gem_seamless",  name: "GEM (Canadian)"  },
      { id: "icon_seamless", name: "ICON (German)"   },
    ];

    const baseUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&daily=temperature_2m_max,temperature_2m_min,precipitation_sum` +
      `&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=auto&forecast_days=${days}`;

    const results = await Promise.allSettled(
      MODELS.map(m => fetch(`${baseUrl}&models=${m.id}`).then(r => r.json()))
    );

    const dates = results.find(r => r.status === "fulfilled" && r.value?.daily?.time?.length)?.value?.daily?.time ?? [];
    if (!dates.length) {
      const errors = results.map((r, i) => `${MODELS[i].name}: ${r.status === "rejected" ? r.reason?.message : r.value?.reason ?? "no data"}`).join("\n");
      return { content: [{ type: "text", text: `Model comparison unavailable for this location — no data returned.\n\n${errors}\n\nTry a nearby city or check that the location geocoded correctly.` }] };
    }

    const lines = [`Model Forecast Comparison — ${placeName} (${days}-day)\n${"─".repeat(48)}`];
    lines.push(`Format: High°F / Low°F   Precip"`);

    for (let i = 0; i < Math.min(days, dates.length); i++) {
      lines.push(`\n${dates[i]}:`);
      const dayHighs = [], dayLows = [], dayPrecip = [];

      for (let m = 0; m < MODELS.length; m++) {
        const r = results[m];
        if (r.status !== "fulfilled") { lines.push(`  ${MODELS[m].name.padEnd(18)}: unavailable`); continue; }
        const d = r.value.daily;
        const high   = d?.temperature_2m_max?.[i];
        const low    = d?.temperature_2m_min?.[i];
        const precip = d?.precipitation_sum?.[i];
        if (high == null) { lines.push(`  ${MODELS[m].name.padEnd(18)}: no data`); continue; }

        dayHighs.push(high);
        if (low  != null) dayLows.push(low);
        if (precip != null) dayPrecip.push(precip);

        const precipStr = precip != null ? `   ${precip.toFixed(2)}"` : "";
        lines.push(`  ${MODELS[m].name.padEnd(18)}: ${Math.round(high)}° / ${low != null ? Math.round(low) + "°" : " ?"}${precipStr}`);
      }

      // Agreement summary for this day
      if (dayHighs.length >= 2) {
        const spreadHigh = Math.max(...dayHighs) - Math.min(...dayHighs);
        const spreadLow  = dayLows.length >= 2 ? Math.max(...dayLows) - Math.min(...dayLows) : null;
        const spreadPrecip = dayPrecip.length >= 2 ? Math.max(...dayPrecip) - Math.min(...dayPrecip) : null;
        const agreement = spreadHigh <= 3 ? "Good agreement" : spreadHigh <= 7 ? "Moderate spread" : "Poor agreement — low confidence";
        const spreadNote = spreadLow != null ? ` | lows: ${Math.round(spreadLow)}°F spread` : "";
        lines.push(`  → ${agreement} (highs: ${Math.round(spreadHigh)}°F spread${spreadNote})`);
        if (spreadPrecip != null && spreadPrecip > 0.25) {
          lines.push(`  → Precip uncertainty: ${spreadPrecip.toFixed(2)}" spread between models`);
        }
      }
    }

    const failed = results.filter(r => r.status === "rejected").length;
    if (failed > 0) lines.push(`\nNote: ${failed} model(s) returned no data for this location.`);
    lines.push(`\nSource: Open-Meteo multi-model API — GFS, ECMWF IFS/AIFS, GEM, ICON`);
    return { content: [{ type: "text", text: lines.join("\n") }] };
  }
);

// ────────────────────────────────────────────────────────────────────────────
// Severe Weather Nowcast agent — called by /nowcast HTTP endpoint

async function runSevereWeatherNowcast(lat, lon) {
  let stateCode = null;
  try {
    const ptRes = await fetch(`https://api.weather.gov/points/${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
    if (ptRes.ok) {
      const pt = await ptRes.json();
      stateCode = pt.properties?.relativeLocation?.properties?.state ?? null;
    }
  } catch (_) {}

  const [alertsRes, spcRes, stormRptRes, condRes] = await Promise.allSettled([
    fetch(`https://api.weather.gov/alerts/active?point=${lat.toFixed(4)},${lon.toFixed(4)}&status=actual`, { headers: NWS_HEADERS }).then(r => r.ok ? r.json() : null),
    fetch("https://www.spc.noaa.gov/products/outlook/day1otlk.txt").then(r => r.ok ? r.text() : ""),
    fetch("https://www.spc.noaa.gov/climo/reports/today.csv").then(r => r.ok ? r.text() : ""),
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,windspeed_10m,winddirection_10m,weathercode,relativehumidity_2m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto`).then(r => r.ok ? r.json() : null),
  ]);

  const alerts = [];
  if (alertsRes.status === "fulfilled" && alertsRes.value?.features) {
    alertsRes.value.features.forEach(f => alerts.push({
      event: f.properties?.event ?? "Unknown",
      severity: f.properties?.severity ?? "Unknown",
      headline: f.properties?.headline ?? "",
    }));
  }

  let spcLevel = "NONE", spcExcerpt = "No SPC data available.";
  if (spcRes.status === "fulfilled" && spcRes.value) {
    const t = spcRes.value;
    if (/HIGH RISK/i.test(t)) spcLevel = "HIGH";
    else if (/MODERATE RISK/i.test(t)) spcLevel = "MODERATE";
    else if (/ENHANCED RISK/i.test(t)) spcLevel = "ENHANCED";
    else if (/SLIGHT RISK/i.test(t)) spcLevel = "SLIGHT";
    else if (/MARGINAL RISK/i.test(t)) spcLevel = "MARGINAL";
    const lines = t.split("\n").map(l => l.trim()).filter(Boolean);
    const s = lines.findIndex(l => /THERE IS|SLIGHT|MARGINAL|ENHANCED|MODERATE|HIGH|NO SEVERE/.test(l));
    if (s >= 0) spcExcerpt = lines.slice(s, s + 4).join(" ").slice(0, 400);
  }

  const stormReports = { tornadoes: 0, hail: 0, wind: 0, total: 0 };
  if (stormRptRes.status === "fulfilled" && stormRptRes.value) {
    stormRptRes.value.split("\n").slice(1).forEach(l => {
      const cols = l.split(",");
      const type = cols[0]?.trim(), st = cols[5]?.trim()?.toUpperCase();
      if (!stateCode || st === stateCode) {
        if (type === "T") { stormReports.tornadoes++; stormReports.total++; }
        else if (type === "H") { stormReports.hail++; stormReports.total++; }
        else if (type === "W") { stormReports.wind++; stormReports.total++; }
      }
    });
  }

  let currentConditions = null;
  if (condRes.status === "fulfilled" && condRes.value) {
    const c = condRes.value.current;
    currentConditions = {
      temp: c?.temperature_2m != null ? Math.round(c.temperature_2m) : null,
      wind: c?.windspeed_10m != null ? Math.round(c.windspeed_10m) : null,
      windDir: c?.winddirection_10m != null ? dirToCardinal(c.winddirection_10m) : null,
      humidity: c?.relativehumidity_2m ?? null,
      condition: WMO[c?.weathercode] ?? "Unknown",
    };
  }

  const tornadoWarning = alerts.some(a => a.event.includes("Tornado Warning"));
  const tornadoWatch   = alerts.some(a => a.event.includes("Tornado Watch"));
  const svreWarning    = alerts.some(a => a.event.includes("Severe Thunderstorm Warning"));
  const svreWatch      = alerts.some(a => a.event.includes("Severe Thunderstorm Watch"));

  let threatLevel;
  if (tornadoWarning || alerts.some(a => a.severity === "Extreme")) threatLevel = "EXTREME";
  else if (spcLevel === "HIGH")                                       threatLevel = "HIGH";
  else if (tornadoWatch || spcLevel === "MODERATE")                   threatLevel = "MODERATE";
  else if (svreWarning  || spcLevel === "ENHANCED")                   threatLevel = "ELEVATED";
  else if (svreWatch    || spcLevel === "SLIGHT")                     threatLevel = "LOW";
  else if (spcLevel === "MARGINAL")                                   threatLevel = "MARGINAL";
  else                                                                threatLevel = "NONE";

  const { headline, whyItMatters } = generateSevereNarrative(threatLevel, spcLevel, stormReports, stateCode);

  const activeThreats = [];
  if (tornadoWarning) activeThreats.push({ type: "Tornado Warning",             severity: "EXTREME"  });
  if (tornadoWatch)   activeThreats.push({ type: "Tornado Watch",               severity: "HIGH"     });
  if (svreWarning)    activeThreats.push({ type: "Severe Thunderstorm Warning", severity: "ELEVATED" });
  if (svreWatch)      activeThreats.push({ type: "Severe Thunderstorm Watch",   severity: "LOW"      });
  alerts.filter(a =>
    !["Tornado Warning","Tornado Watch","Severe Thunderstorm Warning","Severe Thunderstorm Watch"].some(t => a.event.includes(t)) &&
    ["Extreme","Severe"].includes(a.severity)
  ).slice(0, 3).forEach(a => activeThreats.push({ type: a.event, severity: a.severity.toUpperCase() }));

  return {
    location: { lat: parseFloat(lat.toFixed(4)), lon: parseFloat(lon.toFixed(4)), state: stateCode },
    timestamp: new Date().toISOString(),
    threatLevel, headline, whyItMatters,
    currentConditions, activeThreats,
    spc: { level: spcLevel, excerpt: spcExcerpt },
    stormReports, totalAlerts: alerts.length,
  };
}

function generateSevereNarrative(threatLevel, spcLevel, stormReports, state) {
  const sl = state ?? "this area";
  const rpt = stormReports.total > 0
    ? ` Today's reports in ${sl}: ${[
        stormReports.tornadoes > 0 ? stormReports.tornadoes + " tornado(es)" : "",
        stormReports.hail > 0      ? stormReports.hail + " large hail"      : "",
        stormReports.wind > 0      ? stormReports.wind + " damaging wind"   : "",
      ].filter(Boolean).join(", ")}.`
    : "";
  switch (threatLevel) {
    case "EXTREME":  return { headline: "TORNADO WARNING — Take shelter immediately", whyItMatters: "A tornado warning means rotation has been detected by radar or a tornado has been sighted. This is the highest-urgency alert in the NWS system. Move to an interior room on the lowest floor, away from windows. Do not wait for visual confirmation." };
    case "HIGH":     return { headline: "HIGH RISK — Major severe weather outbreak likely", whyItMatters: `SPC High Risk is issued fewer than 5 times per year and signals a widespread, high-confidence outbreak. Multiple tornadoes (some violent EF3+), significant hail, and destructive winds are all possible. This is a life-threatening situation.${rpt}` };
    case "MODERATE": return { headline: "MODERATE RISK — Significant severe weather likely", whyItMatters: `SPC Moderate Risk means a notable event is expected in ${sl}. This level is reserved for high-confidence days with multiple tornadoes or large hail likely. Instability and wind shear support supercell development. Know your shelter.${rpt}` };
    case "ELEVATED": return { headline: "ELEVATED RISK — Severe thunderstorms likely", whyItMatters: `SPC Enhanced Risk or active severe warnings indicate organized severe weather is occurring or expected. Supercells capable of tornadoes, large hail (1"+), and winds above 58 mph are possible. Have a shelter plan ready.${rpt}` };
    case "LOW":      return { headline: "LOW RISK — Isolated severe weather possible", whyItMatters: `SPC Slight Risk or an active severe thunderstorm watch means conditions support scattered severe weather. Isolated supercells could produce tornadoes, hail, or damaging winds. Stay weather-aware.${rpt}` };
    case "MARGINAL": return { headline: "MARGINAL RISK — Low but nonzero severe threat", whyItMatters: `SPC Marginal Risk — the lowest categorical level — means some storms may briefly become severe. Typical hazards: quarter-size hail or 58 mph gusts. No significant event expected.${rpt}` };
    default:         return { headline: "No significant severe weather threat", whyItMatters: `NWS data and SPC outlook show no active severe weather threats for this location.${rpt} Conditions remain below severe thresholds.` };
  }
}

// ────────────────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);

// Startup diagnostics — written to stderr so they appear in Claude Desktop's MCP log
if (!existsSync(WINDNINJA_CLI)) {
  process.stderr.write(`[stormwatch] WARNING: WindNinja CLI not found at ${WINDNINJA_CLI} — tools 15 and /windninja will fail.\n`);
} else {
  process.stderr.write(`[stormwatch] WindNinja CLI confirmed at ${WINDNINJA_CLI}\n`);
}

// ── HTTP server for StormWatch Live HTML integration ─────────────────────────
// Exposes WindNinja as a local REST endpoint so the map app can fetch grid data.
// Runs on localhost:3456 — CORS open for file:// and localhost origins.

const WINDNINJA_HTTP_PORT = 3456;
const VALID_VEG = new Set(["grass", "brush", "trees"]);

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Content-Type", "application/json");

  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url, "http://localhost");

  if (url.pathname === "/health") {
    res.end(JSON.stringify({ status: "ok", server: "stormwatch", version: "4.0.0" }));
    return;
  }

  if (url.pathname === "/windninja") {
    const lat   = parseFloat(url.searchParams.get("lat")    ?? "NaN");
    const lon   = parseFloat(url.searchParams.get("lon")    ?? "NaN");
    const speed = parseFloat(url.searchParams.get("speed")  ?? "10");
    const dir   = parseFloat(url.searchParams.get("dir")    ?? "270");
    const radius = parseFloat(url.searchParams.get("radius") ?? "5");
    const rawVeg = url.searchParams.get("veg") ?? "grass";
    const veg   = VALID_VEG.has(rawVeg) ? rawVeg : "grass";

    if (isNaN(lat) || isNaN(lon)) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: "lat and lon are required" }));
      return;
    }

    try {
      const { vel, angData, demCached } = await runWindNinjaCore(lat, lon, speed, dir, radius, veg);
      if (!vel.data.length) throw new Error("WindNinja output was empty");

      // Subsample to ≤10×10 grid so the map stays readable
      const step = Math.max(1, Math.floor(Math.min(vel.nrows, vel.ncols) / 10));
      const vectors = [];
      for (let r = 0; r < vel.nrows; r += step) {
        for (let c = 0; c < vel.ncols; c += step) {
          const idx = r * vel.ncols + c;
          const spd = vel.data[idx];
          if (spd == null || isNaN(spd) || spd < 0.5) continue;
          const cellLat = vel.yll + (vel.nrows - 1 - r) * vel.cell;
          const cellLon = vel.xll + c * vel.cell;
          const cellDir = angData?.[idx] ?? dir;
          vectors.push({
            lat: parseFloat(cellLat.toFixed(5)),
            lon: parseFloat(cellLon.toFixed(5)),
            speed: parseFloat(spd.toFixed(1)),
            dir: Math.round(cellDir % 360),
          });
        }
      }

      const allSpeeds = vel.data.filter(v => v >= 0.5);
      const sorted = [...allSpeeds].sort((a, b) => a - b);
      let sMin = Infinity, sMax = -Infinity;
      for (const v of allSpeeds) { if (v < sMin) sMin = v; if (v > sMax) sMax = v; }
      res.end(JSON.stringify({
        input: { speed, dir, radius, veg, demCached },
        stats: {
          min:  sMin === Infinity ? null : sMin.toFixed(1),
          max:  sMax === -Infinity ? null : sMax.toFixed(1),
          mean: (allSpeeds.reduce((a, b) => a + b, 0) / allSpeeds.length).toFixed(1),
          p10:  sorted[Math.floor(sorted.length * 0.10)]?.toFixed(1),
          p90:  sorted[Math.floor(sorted.length * 0.90)]?.toFixed(1),
        },
        vectors,
      }));
    } catch (err) {
      process.stderr.write(`[stormwatch] /windninja error: ${err.message}\n`);
      res.writeHead(500);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  if (url.pathname === "/nowcast") {
    const lat = parseFloat(url.searchParams.get("lat") ?? "NaN");
    const lon = parseFloat(url.searchParams.get("lon") ?? "NaN");
    if (isNaN(lat) || isNaN(lon)) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: "lat and lon are required" }));
      return;
    }
    try {
      const result = await runSevereWeatherNowcast(lat, lon);
      res.end(JSON.stringify(result));
    } catch (err) {
      process.stderr.write(`[stormwatch] /nowcast error: ${err.message}\n`);
      res.writeHead(500);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
}).on('error', (err) => {
  if (err.code !== 'EADDRINUSE') throw err;
  process.stderr.write(`[stormwatch] HTTP server: port ${WINDNINJA_HTTP_PORT} already in use — skipping HTTP, all stdio MCP tools continue.\n`);
}).listen(WINDNINJA_HTTP_PORT, "127.0.0.1", () => {
  process.stderr.write(`[stormwatch] HTTP server listening on 127.0.0.1:${WINDNINJA_HTTP_PORT}\n`);
});
