// StormWatch Cloud — public backend (Cloudflare Worker)
// -----------------------------------------------------------------------------
// This is a SEPARATE copy of ONE StormWatch backend endpoint (the Fire agent),
// packaged so it can run in the cloud and be called by the public GitHub Pages
// site. It does NOT touch or replace the local mcp-server — that keeps powering
// Claude Desktop and your local app exactly as before.
//
// Routes:
//   GET /health                     → { status: "ok" }
//   GET /fire-agent?lat=..&lon=..    → fire-risk JSON (same shape as local :3456)
//
// Everything here is plain "fetch public NOAA/Open-Meteo data + do math".

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// Contact string for the NWS API. Placeholder only — never a real email (public repo).
const NWS_HEADERS = { "User-Agent": "StormWatchCloud/1.0 (+https://github.com/aphilp1/stormwatch-live)" };

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

    const url = new URL(request.url);

    if (url.pathname === "/") {
      return new Response(
`<!doctype html><html><head><meta charset="utf-8"><title>StormWatch Cloud</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,sans-serif;background:#0a1420;color:#e8f0f8;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
main{max-width:34rem;padding:2rem;line-height:1.6}h1{font-size:1.3rem;color:#ffb066}code{background:#16283e;padding:2px 6px;border-radius:4px;font-size:.85em}
a{color:#7ab8ff}p{color:#a8bcd0}</style></head><body><main>
<h1>&#9889; StormWatch Cloud</h1>
<p>This is the always-on backend for <a href="https://aphilp1.github.io/stormwatch-live/">StormWatch Live</a>.
It has no pages of its own &mdash; it answers data requests from the app.</p>
<p>Status: <a href="/health">/health</a><br>
Fire agent example: <a href="/fire-agent?lat=34.05&amp;lon=-118.25">/fire-agent?lat=34.05&amp;lon=-118.25</a></p>
</main></body></html>`,
        { headers: { ...CORS, "Content-Type": "text/html;charset=utf-8" } });
    }

    if (url.pathname === "/health") {
      return json({ status: "ok", server: "stormwatch-cloud", version: "1.0.0" });
    }

    if (url.pathname === "/fire-agent") {
      const lat = parseFloat(url.searchParams.get("lat") ?? "NaN");
      const lon = parseFloat(url.searchParams.get("lon") ?? "NaN");
      if (isNaN(lat) || isNaN(lon)) return json({ error: "lat and lon are required" }, 400);
      try {
        return json(await runFireWeatherAgent(lat, lon));
      } catch (err) {
        return json({ error: err.message }, 500);
      }
    }

    return json({ error: "not found", routes: ["/health", "/fire-agent?lat=&lon="] }, 404);
  },
};

// ── Fire Weather Agent — ported verbatim from mcp-server/index.js (:3456) ──────
async function runFireWeatherAgent(lat, lon) {
  let placeName = `${lat.toFixed(2)}°N, ${Math.abs(lon).toFixed(2)}°W`;
  let stateCode = null;
  try {
    const ptRes = await fetch(`https://api.weather.gov/points/${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
    if (ptRes.ok) {
      const pt = await ptRes.json();
      const rl = pt.properties?.relativeLocation?.properties;
      if (rl) { placeName = `${rl.city}, ${rl.state}`; stateCode = rl.state; }
    }
  } catch (_) {}

  const yesterday = new Date(Date.now() - 86400000).toISOString().split("T")[0];
  const d90ago    = new Date(Date.now() - 90 * 86400000).toISOString().split("T")[0];

  const [archiveRes, currentRes, spcFireRes, alertsRes] = await Promise.allSettled([
    fetch(
      `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}` +
      `&start_date=${d90ago}&end_date=${yesterday}` +
      `&daily=precipitation_sum,et0_fao_evapotranspiration&precipitation_unit=inch&timezone=auto`
    ).then(r => r.json()),
    fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&hourly=relative_humidity_2m,windspeed_10m,windgusts_10m,temperature_2m,soil_moisture_0_to_1cm` +
      `&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1`
    ).then(r => r.json()),
    fetch("https://www.spc.noaa.gov/products/fire_weather/fwdy1.txt").then(r => r.ok ? r.text() : ""),
    fetch(`https://api.weather.gov/alerts/active?point=${lat.toFixed(4)},${lon.toFixed(4)}&status=actual`, { headers: NWS_HEADERS }).then(r => r.ok ? r.json() : null),
  ]);

  let score = 0;
  const factors = [];
  let total90 = null, sinceRain = null, dryDays = null;
  let temp = null, rh = null, wind = null, gusts = null, soilMoisture = null;
  let deficit = null;

  // Factor 1: Fuel drought (90-day precipitation deficit)
  if (archiveRes.status === "fulfilled") {
    const d = archiveRes.value.daily;
    const precip = (d?.precipitation_sum ?? []).filter(v => v != null);
    const et0    = (d?.et0_fao_evapotranspiration ?? []).filter(v => v != null);
    if (precip.length > 0) {
      total90  = precip.reduce((a, b) => a + b, 0);
      dryDays  = precip.filter(v => v < 0.01).length;
      const rev = [...precip].reverse();
      sinceRain = rev.findIndex(v => v >= 0.10);
      if (sinceRain === -1) sinceRain = 90;
      const totalET0 = et0.reduce((a, b) => a + b, 0);
      deficit = et0.length ? parseFloat((totalET0 - total90).toFixed(1)) : null;
      if      (total90 < 0.5) { score += 3; factors.push(`Extreme fuel drought — only ${total90.toFixed(2)}" in 90 days`); }
      else if (total90 < 2.0) { score += 2; factors.push(`Severe fuel drying — ${total90.toFixed(2)}" in 90 days`); }
      else if (total90 < 5.0) { score += 1; factors.push(`Below-normal precip — ${total90.toFixed(2)}" in 90 days`); }
      if (sinceRain >= 30) { score += Math.min(1, Math.floor(sinceRain / 30)); factors.push(`${sinceRain} days since last meaningful rain`); }
    }
  }

  // Factor 2: Current weather conditions
  if (currentRes.status === "fulfilled") {
    const h   = currentRes.value.hourly;
    const now = new Date();
    const idx = Math.max(0, h.time.findIndex(t => new Date(t) >= now));
    rh   = h.relative_humidity_2m?.[idx] ?? null;
    wind = h.windspeed_10m?.[idx] ?? null;
    gusts = h.windgusts_10m?.[idx] ?? null;
    temp = h.temperature_2m?.[idx] ?? null;
    soilMoisture = h["soil_moisture_0_to_1cm"]?.[idx] ?? null;
    if (rh != null) {
      if      (rh < 10) { score += 3; factors.push(`Critical RH ${rh.toFixed(0)}% — below extreme threshold`); }
      else if (rh < 15) { score += 2; factors.push(`Very low RH ${rh.toFixed(0)}%`); }
      else if (rh < 25) { score += 1; factors.push(`Low RH ${rh.toFixed(0)}%`); }
    }
    if (gusts != null) {
      if      (gusts >= 50) { score += 2; factors.push(`Dangerous gusts ${gusts.toFixed(0)} mph`); }
      else if (gusts >= 35) { score += 1; factors.push(`Strong gusts ${gusts.toFixed(0)} mph`); }
    } else if (wind != null && wind >= 25) {
      score += 1; factors.push(`Elevated wind ${wind.toFixed(0)} mph`);
    }
  }

  // Factor 3: SPC fire weather outlook
  let spcLevel = "NONE";
  let spcExcerpt = "";
  if (spcFireRes.status === "fulfilled" && spcFireRes.value) {
    const txt = spcFireRes.value;
    if      (/EXTREME FIRE WEATHER/i.test(txt))  { spcLevel = "EXTREME";  score += 2;   factors.push("SPC Extreme Fire Weather Day"); }
    else if (/CRITICAL FIRE WEATHER/i.test(txt)) { spcLevel = "CRITICAL"; score += 1.5; factors.push("SPC Critical Fire Weather Day"); }
    else if (/ELEVATED FIRE WEATHER/i.test(txt)) { spcLevel = "ELEVATED"; score += 0.5; factors.push("SPC Elevated Fire Weather Day"); }
    const lines = txt.split("\n").map(l => l.trim()).filter(Boolean);
    const s = lines.findIndex(l => /FIRE WEATHER|ELEVATED|CRITICAL|NO CRITICAL|THERE IS/.test(l));
    if (s >= 0) {
      const end = lines.findIndex((l, i) => i > s && l === "&&");
      spcExcerpt = lines.slice(s, end > 0 ? Math.min(end, s + 15) : s + 10).join(" ");
    }
  }

  // Factor 4: Active fire weather NWS alerts
  const fireAlerts = [];
  if (alertsRes.status === "fulfilled" && alertsRes.value?.features) {
    const all = alertsRes.value.features.filter(f => /red flag|fire weather/i.test(f.properties?.event ?? ""));
    if (all.length) { score += 1; factors.push("Active Red Flag Warning / Fire Weather Watch"); }
    all.forEach(f => fireAlerts.push({ event: f.properties.event, expires: f.properties.expires }));
  }

  score = Math.min(10, Math.round(score * 10) / 10);
  const RATING =
    score >= 9 ? "EXTREME" :
    score >= 7 ? "VERY HIGH" :
    score >= 5 ? "HIGH" :
    score >= 3 ? "MODERATE" :
    score >= 1 ? "LOW-MODERATE" : "LOW";

  const campFireAnalog = (dryDays ?? 0) >= 60 && score >= 7;

  const headline =
    score >= 9 ? "Extreme fire weather — life-threatening conditions" :
    score >= 7 ? "Very high fire risk — significant fire spread likely" :
    score >= 5 ? "High fire risk — active fire weather concerns" :
    score >= 3 ? "Moderate fire risk — elevated fuel danger" :
    score >= 1 ? "Low-moderate fire risk" : "No significant fire weather concern";

  return {
    location: { lat, lon, name: placeName, state: stateCode },
    riskScore: score,
    riskRating: RATING,
    headline,
    factors,
    environment: {
      temp:         temp        != null ? Math.round(temp)                  : null,
      rh:           rh          != null ? Math.round(rh)                    : null,
      wind:         wind        != null ? Math.round(wind)                  : null,
      gusts:        gusts       != null ? Math.round(gusts)                 : null,
      soilMoisture: soilMoisture != null ? parseFloat((soilMoisture * 100).toFixed(1)) : null,
      total90:      total90     != null ? total90.toFixed(2)                : null,
      sinceRain,
      dryDays,
      deficit,
    },
    spc: { level: spcLevel, excerpt: spcExcerpt },
    alerts: fireAlerts,
    campFireAnalog,
    timestamp: new Date().toISOString(),
  };
}
