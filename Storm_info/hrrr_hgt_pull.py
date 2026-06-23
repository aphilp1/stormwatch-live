#!/usr/bin/env python3
"""
hrrr_hgt_pull.py — persist HGT (geopotential height, m) of the BC pressure level
per station, alongside bc_speed/bc_level.

Reads HGT at the bc_level (850 hPa offshore/convective, 700 hPa continental) from
HRRR f00 at each event's median peak hour — the SAME file/hour the BC wind came
from (hrrr_bc_pull.py) — at each station's nearest grid cell. Writes
`bc_level_height_m` into hrrr_error_dataset.csv and hrrr_error_dataset_dem.csv.

Why: in the mountainous West the 850 mb surface (~1500 m MSL) sits at or below the
high ridges, so the "850 wind" there is at-or-below-ground air. Storing the real
height makes the station-elev-vs-BC-level gap explicit (e.g. SLEC1 2033 m, HMRC1
2046 m sit above the 850 surface).

Run in the `dem` env (herbie + cfgrib; hrrr311 is broken at numpy). Usage:
  python hrrr_hgt_pull.py --event camp_2018
  python hrrr_hgt_pull.py --all
"""
import argparse, csv, datetime, os, shutil, sys
from collections import defaultdict
import numpy as np
from scipy.spatial import KDTree
from herbie import Herbie

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE    = r"C:\Users\aphil\Documents\Stormwatch\Storm_info"
CSV_SRC = os.path.join(BASE, "hrrr_error_dataset.csv")
CSV_DEM = os.path.join(BASE, "hrrr_error_dataset_dem.csv")
CACHE   = os.path.join(BASE, "hrrr_bc_cache")
COL     = "bc_level_height_m"

REGIME_BC = {
    "diablo_offshore": 850, "diablo_offshore_NW": 850, "diablo_offshore_NE": 850,
    "santa_ana": 850, "chinook_frontrange": 700, "downslope_oregon": 700,
    "frontal_passage": 700, "convective_outflow": 850,
}


def load_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def event_peaks():
    """Mirror hrrr_bc_pull.py: per-event median peak hour + bc_level."""
    rows, _ = load_csv(CSV_SRC)
    ev = defaultdict(lambda: {"regime": "", "stations": []})
    for r in rows:
        if r.get("qc_flag") not in ("KEEP", "CAUTION"):
            continue
        try:
            float(r["speed_err"])
        except Exception:
            continue
        e = r["event_id"]
        ev[e]["regime"] = r.get("synoptic_regime", "")
        # Use the ACTUAL stored bc_level (the level the BC wind came from) so the
        # height matches the wind. Fall back to the regime map only if absent.
        try:
            ev[e].setdefault("bc_level", int(float(r["bc_level"])))
        except Exception:
            pass
        try:
            lat = float(r["lat"]); lon = float(r["lon"])
        except Exception:
            continue
        try:
            dt = datetime.datetime.fromisoformat(r["peak_dt_utc"].replace("Z", "+00:00"))
        except Exception:
            dt = None
        ev[e]["stations"].append({"stid": r["stid"], "lat": lat, "lon": lon, "dt": dt})
    out = {}
    for e, d in ev.items():
        dts = sorted(s["dt"] for s in d["stations"] if s["dt"])
        if not dts:
            continue
        out[e] = {"peak": dts[len(dts) // 2].replace(tzinfo=None),
                  "level": d.get("bc_level") or REGIME_BC.get(d["regime"], 850),
                  "regime": d["regime"], "stations": d["stations"]}
    return out


def get_hgt(peak, level):
    H = Herbie(peak, model="hrrr", product="prs", fxx=0, save_dir=CACHE, verbose=False)
    ds = H.xarray(f":HGT:{level} mb:", remove_grib=False)
    return ds[list(ds.data_vars)[0]] if hasattr(ds, "data_vars") else ds


def extract(da, lats, lons):
    glat = da.latitude.values.ravel(); glon = da.longitude.values.ravel()
    if glon.min() > 0 and np.any(np.array(lons) < 0):
        glon = np.where(glon > 180, glon - 360, glon)
    tree = KDTree(np.column_stack([glat, glon]))
    dist, idx = tree.query(np.column_stack([lats, lons]))
    flat = da.values.ravel()
    return [float(flat[i]) if dd <= 1.0 else None for dd, i in zip(dist, idx)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    peaks = event_peaks()
    targets = sorted(peaks) if a.all else [a.event or "camp_2018"]

    results = {}  # (eid, stid) -> height_m
    for e in targets:
        if e not in peaks:
            print(f"{e}: not in active events"); continue
        d = peaks[e]; st = d["stations"]
        lats = [s["lat"] for s in st]; lons = [s["lon"] for s in st]
        print(f"{e:<20} {d['regime']:<22} {d['peak']:%Y-%m-%d %HZ}  HGT:{d['level']}mb  n={len(st)}")
        try:
            h = extract(get_hgt(d["peak"], d["level"]), lats, lons)
            ok = [x for x in h if x is not None]
            print(f"  extracted {len(ok)}/{len(st)}  domain-mean = {np.mean(ok):.0f} m"
                  if ok else "  NO DATA")
            for s, hv in zip(st, h):
                results[(e, s["stid"])] = hv
        except Exception as ex:
            print(f"  FAIL: {ex}")

    for path in (CSV_SRC, CSV_DEM):
        rows, fields = load_csv(path)
        if COL not in fields:
            # insert right after bc_level if present, else append
            if "bc_level" in fields:
                fields = fields[:fields.index("bc_level") + 1] + [COL] + fields[fields.index("bc_level") + 1:]
            else:
                fields = fields + [COL]
        bak = path + ".pre_hgt.bak"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        for r in rows:
            k = (r["event_id"], r["stid"])
            r[COL] = f"{results[k]:.1f}" if (k in results and results[k] is not None) else r.get(COL, "")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print(f"wrote {os.path.basename(path)}  (+{COL})")


if __name__ == "__main__":
    main()
