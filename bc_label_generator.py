"""
bc_label_generator.py
======================

Inner-loop label generator for the Stormwatch WindNinja hindcast pipeline.

Goal
----
For one event (e.g. Camp Fire, 2018-11-08), sweep WindNinja boundary
conditions (speed x direction x stability), score each candidate against the
RAWS network, and return the BC that best reproduces the observations. That
winning BC is the training label `y*` for the outer-loop map
    f : HRRR synoptic state  ->  WindNinja boundary condition.

This module is the EXPENSIVE, OFFLINE half of the two-loop design. The solver
(WindNinja, via your `get_terrain_wind` MCP tool) is called only here. The ML
training loop never touches it.

How to wire it to your real pipeline
------------------------------------
Replace `mock_solver` with a function that calls WindNinja / get_terrain_wind:

    def windninja_solver(speed_mph, direction_deg, stability):
        # call get_terrain_wind with this BC, return {station_id: sustained_mph}
        ...
        return {"jarbo_gap": 49.7, "concow": 67.3, ...}

then pass it as `solver=windninja_solver`.

Until herbie + WindNinja are wired in, running this file as-is executes a
SELF-TEST: it plants a known "true" BC, generates synthetic observations from
the mock solver, and confirms the optimizer recovers the planted BC. That
proves the search/scoring machinery works before real data arrives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. CONFIG  --  edit this block per event
# ---------------------------------------------------------------------------

# Observed RAWS peak gusts (mph). Fill in real values; use None for stations
# you don't have obs for (they're excluded from scoring).
#
# Station network from peer-reviewed literature (Brewer & Clements 2020;
# Mass et al. 2021 BAMS). Concow/Paradise/Pulga had NO dedicated RAWS in 2018.
# Held-out validation targets are Colby Mountain and Saddleback (both >=58 mph
# from literature), not town-named stations that don't exist.
#
# Jarbo Gap coords: 39.735944, -121.488944 (NIFC authoritative, corrected 2026-05-30)
# Jarbo Gap Synoptic ID: JBGC1
# NOTE: 52 mph at Jarbo -- gust or sustained? Resolve from IBHS report Fig 1
# (full gust+sustained curve for 00z Nov 8 -- 12z Nov 9).
OBSERVED_GUSTS: Dict[str, Optional[float]] = {
    "jarbo_gap":     52.0,   # confirmed; gust vs sustained TBD from IBHS report
    "colby_mtn":     None,   # literature: >=58 mph (26 m/s) -- held-out target A
    "saddleback":    None,   # literature: >=58 mph (26 m/s) -- held-out target B
    "openshaw":      None,   # in Mass et al. 2021 station set -- fetch when available
    "humbug":        None,   # in Mass et al. 2021 station set -- fetch when available
}

# Per-station weight in the score (e.g. trust an exposed ridge site more than a
# sheltered valley one). Defaults to 1.0 for any station not listed.
STATION_WEIGHTS: Dict[str, float] = {
    "jarbo_gap":  1.0,
    "colby_mtn":  1.0,   # ridge site, held-out
    "saddleback": 1.0,   # ridge site, held-out
    "openshaw":   0.8,   # lower confidence until coords verified
    "humbug":     0.8,
}

# Gust factor: WindNinja outputs SUSTAINED wind; RAWS reports GUSTS.
#   predicted_gust = sustained_output * GUST_FACTOR
# IMPORTANT: GUST_FACTOR = 1.0 reproduces a direct sustained-vs-gust comparison,
# which is what the existing "Jarbo 49.7 vs observed 52, within 4%" result used.
# A physical gust factor for exposed terrain is ~1.3-1.7. Setting it >1 will
# push the optimal BC speed DOWN. Pin this consciously; it's the single biggest
# lever on the absolute speed of the recovered BC. See note at bottom of file.
GUST_FACTOR: float = 1.0

# HRRR 700 hPa prior (the raw aloft wind over the domain). Once herbie pulls the
# archive, set these. The sweep is regularized toward this prior, and the
# "day-one experiment" compares scoring AT the prior vs at the swept optimum.
HRRR_PRIOR_SPEED: Optional[float] = 25.2   # mph  hrrr_700hpa_campfire.py fxx=2 domain mean
HRRR_PRIOR_DIR:   Optional[float] = 49.8   # deg  hrrr_700hpa_campfire.py fxx=2 domain mean
# Day-one finding (2026-05-30): LARGE speed residual (+9.8 mph). Direction correct.
# HRRR 700hPa underestimates driving wind ~40%. Stability/MSLP gradient features needed.

# Regularization strength: penalty added to the score for departing from the
# HRRR prior. Keeps a sparse station network from over-fitting the BC to wherever
# sensors happen to sit. Units chosen so the two terms are comparable to RMSE(mph).
#   total = rmse_gust  +  REG_SPEED*|dS|  +  REG_DIR*angular_dist_deg
# Set REG_* = 0 to disable. If prior is None, regularization is skipped.
REG_SPEED: float = 0.05   # mph penalty per mph of speed departure
REG_DIR:   float = 0.02   # mph penalty per deg of direction departure

# Search grid.
SPEED_GRID:     List[float] = [round(x, 1) for x in _frange(15.0, 55.0, 2.5)] if False else \
                              [15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35,
                               37.5, 40, 42.5, 45, 47.5, 50, 52.5, 55]
DIRECTION_GRID: List[float] = list(range(0, 360, 15))          # every 15 deg
STABILITY_GRID: List[str]   = ["neutral", "stable", "unstable"]  # solver-defined


# ---------------------------------------------------------------------------
# 2. CORE TYPES
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BC:
    """A WindNinja boundary condition candidate."""
    speed_mph: float
    direction_deg: float          # met convention: direction FROM which wind blows
    stability: str

    def __str__(self) -> str:
        return f"{self.speed_mph:.1f} mph @ {self.direction_deg:.0f}deg ({self.stability})"


@dataclass
class ScoredBC:
    bc: BC
    rmse_gust: float                       # RMSE of predicted vs observed gust (mph)
    reg_penalty: float                     # regularization term (mph-equivalent)
    total: float                           # rmse + penalty (the thing minimized)
    per_station: Dict[str, float] = field(default_factory=dict)  # pred gust by station


# A solver maps a BC to {station_id: sustained_mph}.
SolverFn = Callable[[float, float, str], Dict[str, float]]


# ---------------------------------------------------------------------------
# 3. GEOMETRY / SCORING HELPERS
# ---------------------------------------------------------------------------

def angular_distance(a_deg: float, b_deg: float) -> float:
    """Smallest absolute angle between two compass bearings, in [0, 180]."""
    d = abs((a_deg - b_deg) % 360.0)
    return min(d, 360.0 - d)


def score_bc(
    bc: BC,
    solver: SolverFn,
    observed: Dict[str, Optional[float]],
    weights: Dict[str, float],
    gust_factor: float,
    prior: Optional[Tuple[float, float]],
    reg_speed: float,
    reg_dir: float,
) -> ScoredBC:
    """Run the solver for one BC and score it against observations."""
    sustained = solver(bc.speed_mph, bc.direction_deg, bc.stability)

    sq_err = 0.0
    wsum = 0.0
    per_station: Dict[str, float] = {}
    for sid, obs in observed.items():
        if obs is None or sid not in sustained:
            continue
        pred_gust = sustained[sid] * gust_factor
        per_station[sid] = pred_gust
        w = weights.get(sid, 1.0)
        sq_err += w * (pred_gust - obs) ** 2
        wsum += w

    if wsum == 0.0:
        raise ValueError(
            "No scorable stations: every OBSERVED_GUSTS entry is None or "
            "missing from the solver output. Fill in at least one observation."
        )

    rmse = math.sqrt(sq_err / wsum)

    reg = 0.0
    if prior is not None:
        prior_speed, prior_dir = prior
        reg += reg_speed * abs(bc.speed_mph - prior_speed)
        reg += reg_dir * angular_distance(bc.direction_deg, prior_dir)

    return ScoredBC(bc=bc, rmse_gust=rmse, reg_penalty=reg,
                    total=rmse + reg, per_station=per_station)


# ---------------------------------------------------------------------------
# 4. THE SWEEP
# ---------------------------------------------------------------------------

def sweep_bcs(
    solver: SolverFn,
    observed: Dict[str, Optional[float]] = None,
    weights: Dict[str, float] = None,
    gust_factor: float = GUST_FACTOR,
    speed_grid: List[float] = None,
    direction_grid: List[float] = None,
    stability_grid: List[str] = None,
    prior: Optional[Tuple[float, float]] = None,
    reg_speed: float = REG_SPEED,
    reg_dir: float = REG_DIR,
    verbose: bool = True,
) -> Tuple[ScoredBC, List[ScoredBC]]:
    """
    Sweep the full BC grid, score each, return (best, all_sorted_ascending).

    Returns the single best ScoredBC plus the full sorted list so you can
    inspect the error surface (e.g. how flat the speed direction is -- a flat
    surface means the network can't constrain that dimension well).
    """
    observed = observed if observed is not None else OBSERVED_GUSTS
    weights = weights if weights is not None else STATION_WEIGHTS
    speed_grid = speed_grid if speed_grid is not None else SPEED_GRID
    direction_grid = direction_grid if direction_grid is not None else DIRECTION_GRID
    stability_grid = stability_grid if stability_grid is not None else STABILITY_GRID

    results: List[ScoredBC] = []
    total = len(speed_grid) * len(direction_grid) * len(stability_grid)
    if verbose:
        print(f"Sweeping {total} BC candidates "
              f"({len(speed_grid)} speeds x {len(direction_grid)} dirs "
              f"x {len(stability_grid)} stab)...")

    for stab in stability_grid:
        for spd in speed_grid:
            for d in direction_grid:
                bc = BC(speed_mph=float(spd), direction_deg=float(d), stability=stab)
                results.append(
                    score_bc(bc, solver, observed, weights, gust_factor,
                             prior, reg_speed, reg_dir)
                )

    results.sort(key=lambda r: r.total)
    return results[0], results


# ---------------------------------------------------------------------------
# 5. DAY-ONE EXPERIMENT  --  raw HRRR BC vs swept optimum
# ---------------------------------------------------------------------------

def day_one_experiment(
    solver: SolverFn,
    prior_speed: float,
    prior_dir: float,
    prior_stability: str = "neutral",
    **sweep_kwargs,
) -> None:
    """
    The first thing to run once herbie pulls the 700 hPa field.

    Compares the score of using the RAW HRRR aloft wind directly as the BC
    against the swept optimum. Close  -> residual framing validated, build the
    cheap linear map. Far apart -> that gap IS the finding (terrain channeling /
    stability not explained by aloft wind alone).
    """
    print("\n" + "=" * 64)
    print("DAY-ONE EXPERIMENT: raw-HRRR-as-BC  vs  swept optimum")
    print("=" * 64)

    raw_bc = BC(prior_speed, prior_dir, prior_stability)
    raw = score_bc(
        raw_bc, solver, OBSERVED_GUSTS, STATION_WEIGHTS, GUST_FACTOR,
        (prior_speed, prior_dir), REG_SPEED, REG_DIR,
    )
    best, _ = sweep_bcs(solver, prior=(prior_speed, prior_dir),
                        verbose=False, **sweep_kwargs)

    print(f"\nRaw HRRR BC : {raw_bc}")
    print(f"   RMSE(gust) = {raw.rmse_gust:5.2f} mph")
    print(f"\nSwept optimum: {best.bc}")
    print(f"   RMSE(gust) = {best.rmse_gust:5.2f} mph")

    dS = best.bc.speed_mph - prior_speed
    dD = best.bc.direction_deg - prior_dir
    dD = (dD + 180) % 360 - 180  # signed, in (-180, 180]
    print(f"\nResidual the outer map must learn:")
    print(f"   Delta speed = {dS:+.1f} mph")
    print(f"   Delta dir   = {dD:+.0f} deg")
    print(f"   RMSE improvement over raw = {raw.rmse_gust - best.rmse_gust:+.2f} mph")

    if abs(dS) <= 5 and abs(dD) <= 20:
        print("\n=> SMALL residual: aloft wind ~ recovers the BC. Residual framing "
              "validated;\n   proceed to the cheap linear map.")
    else:
        print("\n=> LARGE residual: aloft wind alone does NOT explain the terrain "
              "response.\n   The gap is the finding -- prioritize stability / "
              "pressure-gradient features.")


# ---------------------------------------------------------------------------
# 6. REPORTING
# ---------------------------------------------------------------------------

def print_label(best: ScoredBC, observed: Dict[str, Optional[float]] = None) -> None:
    observed = observed if observed is not None else OBSERVED_GUSTS
    print("\n" + "-" * 64)
    print("OPTIMAL BC (training label y*)")
    print("-" * 64)
    print(f"  speed     : {best.bc.speed_mph:.1f} mph")
    print(f"  direction : {best.bc.direction_deg:.0f} deg")
    print(f"  stability : {best.bc.stability}")
    print(f"  RMSE(gust): {best.rmse_gust:.2f} mph   "
          f"(reg penalty {best.reg_penalty:.2f})")
    print("\n  per-station predicted gust vs observed:")
    for sid, pred in best.per_station.items():
        obs = observed.get(sid)
        if obs is None:
            print(f"    {sid:12s}  pred {pred:6.1f}   obs    n/a")
        else:
            print(f"    {sid:12s}  pred {pred:6.1f}   obs {obs:6.1f}   "
                  f"err {pred - obs:+5.1f} mph")


def as_label_dict(best: ScoredBC, hrrr_prior: Optional[Tuple[float, float]]) -> dict:
    """Serialize the label in residual form for the outer-loop training set."""
    d = {
        "bc_speed_mph": best.bc.speed_mph,
        "bc_direction_deg": best.bc.direction_deg,
        "bc_stability": best.bc.stability,
        "rmse_gust_mph": round(best.rmse_gust, 3),
    }
    if hrrr_prior is not None:
        ps, pd = hrrr_prior
        ddir = (best.bc.direction_deg - pd + 180) % 360 - 180
        d.update({
            "hrrr_prior_speed_mph": ps,
            "hrrr_prior_dir_deg": pd,
            "delta_speed_mph": round(best.bc.speed_mph - ps, 3),     # <- regression target
            "delta_dir_sin": round(math.sin(math.radians(ddir)), 4),  # <- target (no wrap)
            "delta_dir_cos": round(math.cos(math.radians(ddir)), 4),  # <- target
        })
    return d


# ---------------------------------------------------------------------------
# 7. MOCK SOLVER + SELF-TEST  (delete once WindNinja is wired in)
# ---------------------------------------------------------------------------

# Per-station amplification factors relative to BC speed, taken from the actual
# Camp Fire result at the 35 mph NE optimum:
#   Jarbo 49.7/35=1.42, Concow 67.3/35=1.92, Paradise 53.8/35=1.54, Pulga 60.5/35=1.73
_BASE_AMP = {
    "jarbo_gap": 1.42,
    "concow":    1.92,
    "paradise":  1.54,
    "pulga":     1.73,
}
# Direction at which each site channels most strongly (deg). NE-ish flow drives
# the canyon; off-axis flow amplifies less. Tuned so the optimum sits near NE.
_PEAK_DIR = {"jarbo_gap": 45, "concow": 45, "paradise": 50, "pulga": 40}


def mock_solver(speed_mph: float, direction_deg: float, stability: str) -> Dict[str, float]:
    """
    Physically-flavored stand-in for WindNinja. Amplifies BC speed per station,
    tapering as flow rotates off each site's channeling axis. Stability nudges
    amplification (stable -> stronger downslope). NOT a real solver -- it exists
    only so the sweep machinery runs and self-tests before herbie/WindNinja.
    """
    stab_mult = {"stable": 1.08, "neutral": 1.0, "unstable": 0.92}.get(stability, 1.0)
    out: Dict[str, float] = {}
    for sid, amp in _BASE_AMP.items():
        off = angular_distance(direction_deg, _PEAK_DIR[sid])
        taper = max(0.5, math.cos(math.radians(off)))  # full on-axis, halved off-axis
        out[sid] = speed_mph * amp * taper * stab_mult
    return out


def _self_test() -> None:
    """Plant a true BC, synthesize obs, confirm the sweep recovers it."""
    print("SELF-TEST (mock solver) -- no real data required")
    print("=" * 64)
    true_bc = BC(35.0, 45.0, "stable")
    synth = mock_solver(true_bc.speed_mph, true_bc.direction_deg, true_bc.stability)
    planted_obs = {sid: round(v * GUST_FACTOR, 1) for sid, v in synth.items()}
    print(f"Planted true BC : {true_bc}")
    print(f"Synthetic obs   : "
          + ", ".join(f"{k}={v}" for k, v in planted_obs.items()))

    best, allr = sweep_bcs(
        mock_solver, observed=planted_obs, weights={},
        prior=(HRRR_PRIOR_SPEED, HRRR_PRIOR_DIR),
    )
    print_label(best, observed=planted_obs)

    ok = (abs(best.bc.speed_mph - 35.0) <= 2.5
          and angular_distance(best.bc.direction_deg, 45.0) <= 15
          and best.bc.stability == "stable")
    print(f"\nRecovered planted BC within tolerance: {'PASS' if ok else 'FAIL'}")

    print("\nLabel as written to the outer-loop training set:")
    import json
    print(json.dumps(
        as_label_dict(best, (HRRR_PRIOR_SPEED, HRRR_PRIOR_DIR)), indent=2))


def _frange(a, b, step):  # tiny helper (kept for the SPEED_GRID one-liner)
    x = a
    while x <= b + 1e-9:
        yield x
        x += step


if __name__ == "__main__":
    # With the mock solver, run the self-test AND a demo of the day-one
    # experiment. When you wire in WindNinja, replace `mock_solver` below with
    # your real solver and fill in OBSERVED_GUSTS + HRRR_PRIOR_*.
    _self_test()

    # Demo of the day-one experiment using planted synthetic obs so it runs now.
    synth = mock_solver(35.0, 45.0, "stable")
    OBSERVED_GUSTS.update({k: round(v * GUST_FACTOR, 1) for k, v in synth.items()})
    day_one_experiment(mock_solver, prior_speed=HRRR_PRIOR_SPEED,
                       prior_dir=HRRR_PRIOR_DIR, prior_stability="neutral")
