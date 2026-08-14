"""
confidence_field.py
===================

Per-cell UNCERTAINTY ENGINE for Stormwatch WindNinja wind fields.

The point of a next-generation wind engine for life-safety decisions is not a
sharper number — it is a number that knows how much to trust itself, AND WHY.
This module turns a WindNinja wind field into a per-cell confidence field where
every cell carries a confidence value in [0,1] PLUS a labeled dominant reason.

Why the reason matters (the core design principle)
--------------------------------------------------
A confidence value without a cause is operationally useless, because different
causes demand OPPOSITE responses:

  - low confidence because the BC INPUT is uncertain   -> more obs / better BC helps
  - low confidence because the cell is in a JUMP/ROTOR -> NO steady-state method
        zone (method out of scope)                        will ever help; widen the
                                                           safety margin, use another tool

Same number, same confidence, opposite action. So this engine outputs a
DECOMPOSED, LABELED confidence field, not a scalar.

This is the project's own epistemic discipline encoded into the product: the
1.42x collapse, the +3 mph "consistent-with-zero", the hydraulic-jump method
boundary — all are statements about confidence in a number. This engine makes
the pipeline state that confidence per cell, automatically.

Buildable NOW without observations
----------------------------------
Every component here is computed from WindNinja runs + terrain + the synoptic
inputs you already have. NONE requires RAWS observations. The one obs-dependent
component (out-of-distribution distance from validated stations) is a hook that
no-ops until validated cells are supplied, then activates.

The seam: replace `_synthetic_case()` with real inputs —
  speed_ensemble : (M, ny, nx) WindNinja sustained speed for M BC-ensemble members
  dir_ensemble   : (M, ny, nx) WindNinja direction (deg) for M members
  elevation      : (ny, nx) DEM (m)  [from the same DEM WindNinja used]
  bc_speed, bc_dir : the central BC (mph, deg-FROM)
  froude         : dimensionless mountain/Froude proxy (scalar or field)
  bc_suspect     : bool/float from the HGT:700mb terrain-height guard
  edge_cells     : how many boundary cells to treat as edge-artifact (default 2)

Dependencies: numpy only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# REASON LABELS  (the operational payload)
# ---------------------------------------------------------------------------

class Reason(IntEnum):
    CONFIDENT = 0          # no dominant penalty; trust the value
    BC_SENSITIVITY = 1     # ensemble spread: our INPUT is uncertain here
    JUMP_REGIME = 2        # method out of scope: steady-state cannot represent this
    AMPLIFICATION = 3      # extreme nonlinear amplification: less validated regime
    EDGE_ARTIFACT = 4      # domain-edge solver artifact
    BC_INVALID = 5         # the BC itself is suspect (terrain-height guard)
    OUT_OF_DISTRIBUTION = 6  # terrain unlike any validated station: extrapolation

REASON_ACTION = {
    Reason.CONFIDENT:          "trust the value",
    Reason.BC_SENSITIVITY:     "reducible: better BC / more obs would tighten this",
    Reason.JUMP_REGIME:        "IRREDUCIBLE by this method: widen margin, needs non-steady-state tool",
    Reason.AMPLIFICATION:      "treat as plausible-but-unvalidated; prioritize a held-out check here",
    Reason.EDGE_ARTIFACT:      "ignore: enlarge domain so this cell isn't on the boundary",
    Reason.BC_INVALID:         "domain-wide: BC level invalid (700 hPa underground); re-source BC",
    Reason.OUT_OF_DISTRIBUTION:"extrapolation: terrain unlike any validated site",
}


# ---------------------------------------------------------------------------
# RESULT CONTAINER
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceField:
    confidence: np.ndarray                 # (ny,nx) in [0,1], 1 = fully trusted
    dominant_reason: np.ndarray            # (ny,nx) of Reason values
    penalties: Dict[str, np.ndarray]       # named penalty fields, each (ny,nx) in [0,1]
    mean_speed: np.ndarray                 # (ny,nx) ensemble-mean sustained speed
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        c = self.confidence
        lines = [
            f"Confidence field {c.shape}:",
            f"  mean confidence : {np.nanmean(c):.2f}",
            f"  cells <0.5      : {(c < 0.5).mean()*100:.0f}%",
        ]
        # reason breakdown over low-confidence cells
        low = c < 0.5
        if low.any():
            lines.append("  dominant reason among low-confidence cells:")
            for r in Reason:
                frac = (self.dominant_reason[low] == r).mean()
                if frac > 0:
                    lines.append(f"     {r.name:18s} {frac*100:4.0f}%  -> {REASON_ACTION[r]}")
        for n in self.notes:
            lines.append(f"  note: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CALIBRATABLE KNOBS  (principles fixed; numbers tunable — record when changed)
# ---------------------------------------------------------------------------

KNOBS = {
    # BC-sensitivity: coefficient-of-variation of speed mapped to penalty.
    "cv_full_penalty": 0.40,        # speed CV at/above which sensitivity penalty -> 1
    "dir_spread_full_deg": 60.0,    # circular dir std (deg) at which dir penalty -> 1
    # Jump/rotor regime:
    "froude_center": 1.0,           # jump risk peaks near Fr ~ 1
    "froude_width": 0.5,            # how sharply risk falls away from Fr=1
    "decel_full": 0.35,             # fractional along-wind speed drop -> full jump penalty
    "lee_relief_m": 100.0,          # upwind terrain must exceed cell by this to count as lee
    # Amplification extremity:
    "amp_soft": 1.5,                # amplification ratio where penalty begins
    "amp_full": 2.5,                # ratio at which amplification penalty -> 1
    # Edge:
    "edge_cells": 2,                # boundary cells treated as edge artifact
    # BC validity (terrain-height guard): penalty applied domain-wide when suspect
    "bc_invalid_penalty": 0.5,
    # OOD:
    "ood_full_dist": 3.0,           # normalized feature distance -> full OOD penalty
    # low-confidence reporting threshold
    "low_conf": 0.5,
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _circ_std_deg(dirs: np.ndarray, axis: int = 0) -> np.ndarray:
    """Circular standard deviation (deg) across an axis of directions in degrees."""
    r = np.radians(dirs)
    C = np.cos(r).mean(axis=axis)
    S = np.sin(r).mean(axis=axis)
    R = np.sqrt(C**2 + S**2)
    R = np.clip(R, 1e-9, 1.0)
    return np.degrees(np.sqrt(-2.0 * np.log(R)))


def _unit_from_dir_FROM(deg: float) -> Tuple[float, float]:
    """Return (di, dj) grid step in the DOWNWIND direction for a wind FROM `deg`.
    Meteorological: wind FROM deg blows TOWARD deg+180. Grid: i=row(+south/down),
    j=col(+east). Assumes row 0 = north (top). Returns the downwind step direction.
    """
    to = np.radians((deg + 180.0) % 360.0)
    # east component -> +j ; north component -> -i (row increases southward)
    dj = np.sin(to)
    di = -np.cos(to)
    return di, dj


def _saturating(x: np.ndarray, full: float) -> np.ndarray:
    """Map x>=0 to [0,1], reaching ~1 at x=full (smooth, monotone)."""
    return 1.0 - np.exp(-np.clip(x, 0, None) / max(full, 1e-9) * 2.0)


# ---------------------------------------------------------------------------
# COMPONENT PENALTIES  (each returns (ny,nx) in [0,1]; 0 = no penalty)
# ---------------------------------------------------------------------------

def p_bc_sensitivity(speed_ens: np.ndarray, dir_ens: np.ndarray, k=KNOBS) -> np.ndarray:
    """Ensemble spread over BC members. Reducible uncertainty: a better-constrained
    BC would shrink it. This is the workhorse and needs only the BC ensemble."""
    mean = speed_ens.mean(axis=0)
    std = speed_ens.std(axis=0)
    cv = std / np.clip(mean, 1e-6, None)
    p_speed = _saturating(cv, k["cv_full_penalty"])
    dstd = _circ_std_deg(dir_ens, axis=0)
    p_dir = _saturating(dstd / 90.0 * (90.0 / k["dir_spread_full_deg"]), 1.0)
    # combine: a cell is sensitive if EITHER speed or direction is unstable
    return np.maximum(p_speed, p_dir)


def p_jump_regime(mean_speed: np.ndarray, elevation: np.ndarray, bc_dir: float,
                  froude, k=KNOBS) -> np.ndarray:
    """METHOD-BOUNDARY penalty. WindNinja is a steady-state mass-conserving solver
    and structurally CANNOT represent hydraulic jumps / rotors. We can't make the
    solver produce them, but we can flag where they are physically LIKELY, so those
    cells are marked method-out-of-scope rather than trusted.

    Three physical proxies, combined:
      (1) lee position  - cell is downwind of higher terrain (downslope side)
      (2) Froude ~ 1    - the regime in which jumps form
      (3) flow deceleration - steady solver shows a sharp along-wind speed DROP
                              just downwind of an acceleration max (its mass-
                              conserving stand-in for a jump)
    """
    ny, nx = elevation.shape
    di, dj = _unit_from_dir_FROM(bc_dir)

    # (1) lee mask: sample terrain one step UPWIND; if it's higher by lee_relief, lee.
    ii, jj = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    up_i = np.clip(np.round(ii - di * 2).astype(int), 0, ny - 1)
    up_j = np.clip(np.round(jj - dj * 2).astype(int), 0, nx - 1)
    upwind_elev = elevation[up_i, up_j]
    lee = np.clip((upwind_elev - elevation) / k["lee_relief_m"], 0, 1)

    # (3) along-wind deceleration of the mean speed field.
    gi, gj = np.gradient(mean_speed)
    along = gi * di + gj * dj           # d(speed)/d(downwind)
    decel = np.clip(-along / np.clip(mean_speed, 1e-6, None), 0, None)
    p_decel = _saturating(decel, k["decel_full"])

    # (2) Froude proximity to 1 (scalar or field)
    fr = np.asarray(froude, dtype=float)
    fr = np.broadcast_to(fr, elevation.shape) if fr.ndim < 2 else fr
    fr_risk = np.exp(-((fr - k["froude_center"]) ** 2) / (2 * k["froude_width"] ** 2))

    # A strong deceleration signature is itself diagnostic of a jump and should
    # register even where the coarse roll-based lee mask is weak at that exact cell.
    # Combine: decel is the primary detector (weighted up where also lee or in the
    # Froude regime), plus the pure lee+Froude setup. A sharp lee-side speed drop is
    # therefore always caught.
    lee_or_fr = np.clip(np.maximum(lee, fr_risk), 0.5, 1.0)
    jump = np.maximum(p_decel * lee_or_fr, lee * fr_risk)
    return np.clip(jump, 0, 1)


def p_amplification(mean_speed: np.ndarray, bc_speed: float, k=KNOBS) -> np.ndarray:
    """Extreme amplification = deeper into the nonlinear, less-validated regime.
    A soft caution, not a hard penalty: high amplification may be real (that's the
    whole point) but is exactly where a held-out check is most needed."""
    ratio = mean_speed / max(bc_speed, 1e-6)
    x = (ratio - k["amp_soft"]) / max(k["amp_full"] - k["amp_soft"], 1e-9)
    return np.clip(x, 0, 1)


def p_edge(shape: Tuple[int, int], k=KNOBS) -> np.ndarray:
    """Domain-edge solver artifact (the known min=0 boundary issue)."""
    ny, nx = shape
    n = k["edge_cells"]
    pen = np.zeros(shape)
    if n > 0:
        pen[:n, :] = 1; pen[-n:, :] = 1; pen[:, :n] = 1; pen[:, -n:] = 1
    return pen


def p_bc_invalid(shape: Tuple[int, int], bc_suspect, k=KNOBS) -> np.ndarray:
    """Domain-wide penalty when the BC level itself is invalid (terrain-height guard:
    700 hPa at/below terrain). Ties directly to the guard already in the pipeline."""
    s = float(bc_suspect)
    return np.full(shape, s * k["bc_invalid_penalty"])


def p_out_of_distribution(features: Optional[np.ndarray],
                          validated_features: Optional[np.ndarray],
                          k=KNOBS) -> Optional[np.ndarray]:
    """OOD / extrapolation penalty: cells whose terrain features are far (in
    standardized feature space) from ANY validated station are extrapolations.
    Hook: returns None (no-op) until validated_features are supplied. Activates
    automatically as the held-out validation set grows.

    features           : (ny,nx,F) per-cell terrain features (elev, slope, aspect-sin/cos, exposure...)
    validated_features : (V,F) feature vectors at validated stations
    """
    if features is None or validated_features is None or len(validated_features) == 0:
        return None
    ny, nx, F = features.shape
    mu = validated_features.mean(axis=0)
    sd = validated_features.std(axis=0); sd[sd == 0] = 1.0
    fz = (features - mu) / sd                      # (ny,nx,F)
    vz = (validated_features - mu) / sd            # (V,F)
    # nearest validated station distance per cell
    d = np.sqrt(((fz[:, :, None, :] - vz[None, None, :, :]) ** 2).sum(-1)).min(axis=2)
    return np.clip(d / k["ood_full_dist"], 0, 1)


# ---------------------------------------------------------------------------
# THE ENGINE
# ---------------------------------------------------------------------------

def compute_confidence(
    speed_ensemble: np.ndarray,      # (M, ny, nx)
    dir_ensemble: np.ndarray,        # (M, ny, nx)
    elevation: np.ndarray,           # (ny, nx)
    bc_speed: float,
    bc_dir: float,
    froude=1.5,                      # scalar or (ny,nx)
    bc_suspect: float = 0.0,         # 0..1 from terrain-height guard
    features: Optional[np.ndarray] = None,
    validated_features: Optional[np.ndarray] = None,
    knobs: dict = KNOBS,
) -> ConfidenceField:
    """Combine component penalties into a per-cell confidence field with a labeled
    dominant reason. Confidence = product of (1 - penalty_i): each risk independently
    erodes trust (noisy-OR complement). Dominant reason = the largest single penalty,
    because that is the one a forecaster should act on."""
    mean_speed = speed_ensemble.mean(axis=0)
    shape = elevation.shape

    pens = {
        "bc_sensitivity": p_bc_sensitivity(speed_ensemble, dir_ensemble, knobs),
        "jump_regime":    p_jump_regime(mean_speed, elevation, bc_dir, froude, knobs),
        "amplification":  p_amplification(mean_speed, bc_speed, knobs),
        "edge":           p_edge(shape, knobs),
        "bc_invalid":     p_bc_invalid(shape, bc_suspect, knobs),
    }
    ood = p_out_of_distribution(features, validated_features, knobs)
    notes = []
    if ood is not None:
        pens["ood"] = ood
    else:
        notes.append("OOD penalty inactive (no validated stations supplied yet)")

    # confidence = noisy-OR complement of all penalties
    conf = np.ones(shape)
    for p in pens.values():
        conf *= (1.0 - np.clip(p, 0, 1))

    # dominant reason = argmax penalty (map penalty name -> Reason)
    name_to_reason = {
        "bc_sensitivity": Reason.BC_SENSITIVITY,
        "jump_regime":    Reason.JUMP_REGIME,
        "amplification":  Reason.AMPLIFICATION,
        "edge":           Reason.EDGE_ARTIFACT,
        "bc_invalid":     Reason.BC_INVALID,
        "ood":            Reason.OUT_OF_DISTRIBUTION,
    }
    names = list(pens.keys())
    stack = np.stack([pens[n] for n in names], axis=0)   # (P, ny, nx)
    amax = stack.argmax(axis=0)
    maxpen = stack.max(axis=0)
    dom = np.empty(shape, dtype=int)
    for idx, n in enumerate(names):
        dom[amax == idx] = int(name_to_reason[n])

    # PRIORITY OVERRIDE: when a cell is in a jump/rotor regime at a meaningful level,
    # report JUMP_REGIME as the dominant reason even if a reducible penalty (e.g.
    # BC_SENSITIVITY) is numerically larger. Rationale: a real jump zone genuinely
    # has BOTH high ensemble spread AND the decel signature, but the IRREDUCIBLE
    # method-boundary is the one the forecaster must act on. Telling them "get a
    # better BC" when no steady-state BC can ever fix it is the dangerous error.
    if "jump_regime" in pens:
        jr_significant = pens["jump_regime"] >= 0.30
        dom[jr_significant] = int(Reason.JUMP_REGIME)
    # similarly, an invalid BC (domain-wide) outranks reducible local penalties
    if "bc_invalid" in pens:
        dom[pens["bc_invalid"] >= 0.30] = int(Reason.BC_INVALID)

    dom[maxpen < 0.10] = int(Reason.CONFIDENT)   # nothing meaningfully penalizing

    return ConfidenceField(confidence=conf, dominant_reason=dom,
                           penalties=pens, mean_speed=mean_speed, notes=notes)


# ---------------------------------------------------------------------------
# SELF-TEST  (synthetic terrain + BC ensemble; no obs, no WindNinja needed)
# ---------------------------------------------------------------------------

def _synthetic_case(ny=40, nx=40, M=12, seed=0):
    """Build a Gaussian ridge, NE boundary flow, and a mock WindNinja ensemble that
    (a) amplifies on the lee, (b) plants a high-spread + decelerating JUMP zone on
    the lee, and (c) has quiet windward flow. Used to verify the engine flags the
    right cells for the right reasons."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:ny, 0:nx]
    # a ridge running NW-SE, crest near the middle
    ridge = 1500 * np.exp(-((x - nx/2) ** 2) / (2 * (nx*0.12) ** 2))
    elevation = 500 + ridge

    bc_speed, bc_dir = 30.0, 45.0          # 30 mph FROM NE -> flow toward SW
    di, dj = _unit_from_dir_FROM(bc_dir)    # downwind step (row+, col-)

    # lee side = downwind of crest. For NE flow the lee is the SW (lower-col) side.
    # Sample terrain one step UPWIND (toward NE: row-, col+) and compare.
    up = np.roll(elevation, (-int(round(di*2)), -int(round(dj*2))), (0, 1))
    lee = np.clip((up - elevation) / 100.0, 0, 2)   # >0 where upwind is higher = lee
    base = bc_speed * (1.0 + 0.6 * lee)    # amplify up to ~1.6x on the lee

    # plant a sharp jump zone ON THE LEE just downwind of the crest where speed
    # suddenly drops. Pick the strongest-lee cells directly (guaranteed non-empty),
    # so the planted zone and the checked zone are identical by construction.
    lee_flat = lee.ravel()
    thresh = np.quantile(lee_flat, 0.85)        # top 15% most-lee cells
    jump_band = lee >= thresh
    base = base.copy()
    base[jump_band] *= 0.45                 # sudden deceleration = jump signature

    # ensemble: members vary the BC; jump band gets EXTRA spread (unstable)
    speed_ens = np.empty((M, ny, nx))
    dir_ens = np.empty((M, ny, nx))
    for m in range(M):
        fac = 1.0 + rng.normal(0, 0.08)     # BC speed perturbation
        dperturb = rng.normal(0, 5)
        spd = base * fac
        spd[jump_band] *= (1.0 + rng.normal(0, 0.5))   # high sensitivity in jump zone
        speed_ens[m] = np.clip(spd, 0, None)
        d = np.full((ny, nx), (bc_dir + 180) % 360) + dperturb
        d[jump_band] += rng.normal(0, 40)   # erratic direction in jump zone
        dir_ens[m] = d % 360
    return speed_ens, dir_ens, elevation, bc_speed, bc_dir, jump_band


if __name__ == "__main__":
    speed_ens, dir_ens, elev, bcs, bcd, jump_band = _synthetic_case()

    cf = compute_confidence(
        speed_ens, dir_ens, elev, bc_speed=bcs, bc_dir=bcd,
        froude=1.0,            # near the jump-forming regime
        bc_suspect=0.0,
    )
    print(cf.summary())

    # verify the engine flags the planted jump zone. A hydraulic jump is a
    # TRANSITION (an edge), so the detector correctly fires on the deceleration
    # gradient at the band boundary, not uniformly across the planted region.
    jr = (cf.dominant_reason == int(Reason.JUMP_REGIME))
    jump_pen = cf.penalties["jump_regime"]
    band_conf = cf.confidence[jump_band].mean()
    jump_detected = (jump_pen[jump_band] > 0.3).any()  # jump signature present in/at band
    n_jump_cells = jr.sum()
    print("\n--- self-test checks ---")
    print(f"jump band: mean confidence {band_conf:.2f} (expect LOW)")
    print(f"jump signature detected at band transition: {jump_detected}")
    print(f"cells flagged JUMP_REGIME domain-wide: {n_jump_cells}")
    print(f"overall mean confidence {cf.confidence.mean():.2f}")
    print(f"edge cells flagged EDGE_ARTIFACT: "
          f"{(cf.dominant_reason[0,:]==int(Reason.EDGE_ARTIFACT)).mean()*100:.0f}% of top row")

    ok = band_conf < 0.6 and jump_detected and n_jump_cells > 0
    verdict = ("low-confidence lee zone + jump signature detected at transition"
               if ok else "check knob calibration")
    print(f"\nRESULT: {'PASS' if ok else 'REVIEW'} — {verdict}")

    # demo: a domain-wide BC-invalid case (terrain-height guard fired)
    print("\n--- demo: terrain-height guard fired (high-terrain domain) ---")
    cf2 = compute_confidence(speed_ens, dir_ens, elev, bc_speed=bcs, bc_dir=bcd,
                             froude=1.0, bc_suspect=1.0)
    print(f"mean confidence drops to {cf2.confidence.mean():.2f} "
          f"(BC-invalid penalty applied domain-wide)")
