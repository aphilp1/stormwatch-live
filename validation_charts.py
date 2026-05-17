#!/usr/bin/env python3
import sys, math
sys.stdout.reconfigure(encoding='utf-8')

W = 80

def hdr(title):
    print()
    print("=" * W)
    print(f"  {title}")
    print("=" * W)

def row(label, elev, obs, hrrr, gfs, wn, note=""):
    def fmt(pair):
        if pair is None: return f"{'---':^17}"
        d, s = pair
        if d is None: return f"{'blocked':^17}"
        return f"{d:3.0f}° / {s:4.1f} mph"
    n = f"  {note}" if note else ""
    print(f"  {label:<12} {elev:>6}  {fmt(obs):<17}  {fmt(hrrr):<17}  {fmt(gfs):<17}  {fmt(wn):<17}{n}")

def divider(): print("  " + "-" * (W-2))

# ═══════════════════════════════════════════════════════════════════════
#  CHART 1 — December 17, 2025
# ═══════════════════════════════════════════════════════════════════════
hdr("CHART 1 — December 17, 2025  |  NW-Flow Event  |  WindNinja Validation")
print(f"  700 hPa 12z: 315° NW / 29 mph  (OTX = TFX)  |  MST = UTC-7")
print(f"  Validation window: 18-21z (11-14 MST) — cold pool mixed out, surface coupled")
print()
print(f"  {'Station':<12} {'Elev':>6}  {'Obs 18-21z avg':^17}  {'HRRR 3km avg':^17}  {'GFS 13km avg':^17}  {'WindNinja':^17}")
print(f"  {'':12} {'':6}  {'Dir  /  Spd':^17}  {'Dir  /  Spd':^17}  {'Dir  /  Spd':^17}  {'Dir  /  Spd':^17}")
divider()
row("KMSO",  "3205ft", (275, 20.1), (287, 22.6), (270, 25.8), (314, 28.9))
row("PtSix", "6300ft", (None,None), (282, 20.8), (270, 26.9), (315, 28.1), "obs blocked (WRCC)")
row("BluMt", "3412ft", (None,None), (270, 23.6), (266, 24.7), (315, 26.8), "obs: wrong stn in Synoptic")
row("Lolo",  "3200ft", (None,None), (277, 19.2), (270, 22.0), (None,None), "obs blocked; WN outside grid")
divider()
print(f"  {'Ambient':12} {'700hPa':>6}  {'--- observed ---':^17}  {'--- forecast ---':^17}  {'--- forecast ---':^17}  {'315° / 29.0 mph':^17}  (init)")
print()
print("  Model agreement (18-21z coupled window):")
print("    Direction: KMSO obs 275° — HRRR 287°, GFS 270°, WN 314°  (WN closest to 700hPa; valley channels to W)")
print("    Speed:     KMSO obs 20.1 — HRRR 22.6, GFS 25.8, WN 28.9  (all models 10-44% high)")
print("    BluMt/PtSix: WN near-ambient (26-28 mph); HRRR 20-24 mph; GFS 24-27 mph")
print("    No strong terrain acceleration found at correct BLMM8/PtSix coordinates")
print()
print("  BLMM8 location note:")
print("    Authoritative (NIFC RAWS): 46.821°N, -114.101°W  — foothills SE of Missoula")
print("    Earlier assumed (WRCC guess): 46.832°N, -114.216°W — near Blue Mtn ridge (WRONG)")
print("    Impact: prior 38.8 mph WN result was at wrong location; correct value is 26.8 mph")

# ═══════════════════════════════════════════════════════════════════════
#  CHART 2 — July 24, 2024  HRRR hourly
# ═══════════════════════════════════════════════════════════════════════
hdr("CHART 2 — July 24, 2024  |  Missoula Derecho  |  HRRR Pre-Storm Hourly")
print(f"  700 hPa 00z Jul25: 234° SW / 30 mph  (OTX = TFX identical)")
print(f"  Derecho impact: 21:00 MDT = 03z Jul 25  |  MDT = UTC-6")
print()

HRRR_JUL24 = {
    #utc_hr: (KMSO, MPOI, BLMM8, TS897)  dir,spd
    15: ((243, 1.1), (274, 1.0), (360, 0.5), (340, 0.8)),
    16: ((301, 2.1), (319, 2.1), ( 17, 2.0), (345, 2.1)),
    17: ((124, 0.6), ( 22, 0.7), ( 50, 1.6), (337, 1.1)),
    18: ((139, 1.3), ( 34, 0.3), (113, 0.8), (179, 1.7)),
    19: (( 51, 1.4), ( 37, 1.6), ( 95, 2.7), (157, 2.8)),
    20: ((324, 5.3), (334, 5.2), (269, 6.8), (304, 2.4)),
    21: ((253,10.6), (268,13.4), (266, 8.8), (283,13.9)),
    22: ((294,15.2), (299,13.6), (250, 6.7), (275,10.7)),
    23: ((295,14.1), (306,14.1), (276, 7.4), (287,10.0)),
    24: ((298,14.3), (301,14.0), (299,11.4), (308,12.4)),
    25: ((339,13.6), (345, 8.7), (337, 4.8), (338, 8.5)),
    26: ((332,11.7), (339,11.2), (  1, 7.5), ( 25, 8.3)),
    27: ((304, 9.9), (307, 9.7), (305, 9.4), (308, 7.6)),
}

def fds(pair): return f"{pair[0]:3.0f}°/{pair[1]:4.1f}" if pair else "  ---  "

print(f"  {'UTC':^8} {'MDT':^8} | {'KMSO 3205ft':^12} | {'PtSix 6300ft':^12} | {'BluMt 3412ft':^12} | {'Lolo 3200ft':^12} | Phase")
print(f"  {'':8} {'':8} | {'Dir / Spd':^12} | {'Dir / Spd':^12} | {'Dir / Spd':^12} | {'Dir / Spd':^12} |")
divider()

phases = {
    15:"decoupled", 16:"decoupled", 17:"decoupled", 18:"decoupled", 19:"decoupled",
    20:"coupling",  21:"SW builds", 22:"SW peak",   23:"SW peak",
    24:"pre-storm", 25:"pre-storm", 26:"pre-storm", 27:"STORM HIT",
}
for fxx, (km, mp, bl, ts) in HRRR_JUL24.items():
    utc_hr = fxx % 24
    mdt_hr = (fxx - 6) % 24
    day_u = "Jul24" if fxx < 24 else "Jul25"
    day_m = "Jul24" if fxx < 30 else "Jul25"
    phase = phases.get(fxx, "")
    marker = "  <<< DERECHO" if fxx == 27 else ""
    print(f"  {utc_hr:02d}z {day_u[3:]} {mdt_hr:02d}M {day_m[3:]} | {fds(km):^12} | {fds(mp):^12} | {fds(bl):^12} | {fds(ts):^12} | {phase}{marker}")

divider()
print()
print("  Key findings — July 24 2024:")
print("    15-19z (09-13 MDT): Surface completely decoupled — <3 mph, all directions")
print("    20-23z (14-17 MDT): SW/WNW flow builds to 10-15 mph as inversion erodes")
print("    24-27z (18-21 MDT): Shifts NW/NNW then HRRR shows only 8-10 mph at storm time")
print("    HRRR DID NOT CAPTURE derecho downdraft (65-109 mph obs gusts) — convective, not terrain")
print()

# ═══════════════════════════════════════════════════════════════════════
#  CHART 3 — July 24, 2024  WindNinja vs HRRR
# ═══════════════════════════════════════════════════════════════════════
hdr("CHART 3 — July 24, 2024  |  WindNinja vs HRRR  |  SW-Flow Window 21-23z")
print(f"  WindNinja init: 234° SW / 30 mph (700 hPa ambient)")
print(f"  Best comparison: 21-23z (15-17 MDT) when SW flow briefly at surface")
print()
print(f"  {'Station':<12} {'Elev':>6}  {'HRRR 21-23z avg':^17}  {'WindNinja 234/30':^17}  {'NWS LSR obs nearest':^22}")
divider()

# HRRR 21-23z vector averages (computed manually from above data)
# KMSO: (253,10.6), (294,15.2), (295,14.1)
# MPOI: (268,13.4), (299,13.6), (306,14.1)
# BLMM8: (266,8.8), (250,6.7), (276,7.4)
# TS897: (283,13.9), (275,10.7), (287,10.0)

def vec_avg3(triplets):
    us = [-s*math.sin(math.radians(d)) for d,s in triplets]
    vs = [-s*math.cos(math.radians(d)) for d,s in triplets]
    mu,mv = sum(us)/3, sum(vs)/3
    spd = math.sqrt(mu**2+mv**2)
    dirn = math.degrees(math.atan2(-mu,-mv)) % 360
    return dirn, spd

kmso_hrrr  = vec_avg3([(253,10.6),(294,15.2),(295,14.1)])
mpoi_hrrr  = vec_avg3([(268,13.4),(299,13.6),(306,14.1)])
blmm8_hrrr = vec_avg3([(266, 8.8),(250, 6.7),(276, 7.4)])
ts897_hrrr = vec_avg3([(283,13.9),(275,10.7),(287,10.0)])

def fmt2(pair): return f"{pair[0]:3.0f}° / {pair[1]:4.1f} mph"

print(f"  {'KMSO':<12} {'3205ft':>6}  {fmt2(kmso_hrrr):^17}  {'238° / 27.1 mph':^17}  {'gap: stn offline at storm':^22}")
print(f"  {'PtSix':<12} {'6300ft':>6}  {fmt2(mpoi_hrrr):^17}  {'outside grid':^17}  {'blocked (WRCC)':^22}")
print(f"  {'BluMt':<12} {'3412ft':>6}  {fmt2(blmm8_hrrr):^17}  {'outside grid':^17}  {'blocked (WRCC)':^22}")
print(f"  {'Lolo':<12} {'3200ft':>6}  {fmt2(ts897_hrrr):^17}  {'outside grid':^17}  {'72 mph gust at 20:35 MDT*':^22}")
divider()
print(f"  {'Ambient':12} {'700hPa':>6}  {'--- HRRR: ~12 mph SW ---':^17}  {'234° / 30.0 mph':^17}  {'65-109 mph (convective)':^22}")
print()
print("  * CWOP MOMM8 at 46.719N -114.157W (5 SW Lolo): 72 mph measured gust, 20:35 MDT")
print("    All other LSR gusts (81-109 mph) are damage estimates or personal WX stations")
print()
print("  WindNinja note:")
print("    Init at 234°/30 mph = 700 hPa ambient; surface HRRR peak was only ~12 mph SW")
print("    WN models terrain effect on 30 mph SW input — surface never reached that level")
print("    July 24 validation limited: derecho overwhelmed ambient terrain flow")
print("    True terrain wind comparison requires a non-convective SW event at full strength")
print()
