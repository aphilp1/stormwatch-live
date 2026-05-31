"""
bc_outer_trainer.py
===================

Outer-loop trainer for the Stormwatch WindNinja hindcast pipeline.

It learns the map
    f : HRRR synoptic state  ->  WindNinja boundary-condition RESIDUAL
where the residual is measured against the raw HRRR 700 hPa wind:
    target = (delta_speed_mph, delta_dir_sin, delta_dir_cos)

The labels come from bc_label_generator.as_label_dict(...): one dict per
event-hour, each carrying the swept-optimal BC, the HRRR prior, and the
residual targets. This module joins those labels to HRRR synoptic FEATURES,
fits a linear model, and validates with LEAVE-ONE-EVENT-OUT (LOEO).

Why this shape (read before trusting any number)
-------------------------------------------------
* N is tiny. Seven fires, even sliced per hour, is a small-data regime. The
  honest question this answers is "is there ANY learnable signal beyond just
  using the raw HRRR aloft wind?" -- not "what is the precise coefficient on
  the MSLP gradient." Treat large fitted coefficients with suspicion.
* The baseline is delta = 0  (i.e. "use raw HRRR 700 hPa wind directly as the
  BC"). This is the thing every learned model must beat. If ridge can't beat
  delta=0 under LOEO, the residual is either noise or not yet explained by the
  features you have -- and THAT is a finding, not a failure.
* Linear (ridge) first. With this much data an MLP will memorize the events.
  Graduate only when LOEO on the linear model shows real, stable signal AND
  you have the events to justify more capacity.
* LOEO, not random split. Hourly slices within one event are heavily
  correlated; a random split leaks the answer. Hold out whole events.

Direction handling
-------------------
Never regress raw degrees (0/360 wrap corrupts the fit). We fit sin and cos of
the direction residual as two separate targets, then reconstruct the angle with
atan2 and renormalize the (sin,cos) vector to unit length at inference.

Dependencies: numpy only. (scikit-learn optional; a tiny ridge is implemented
here so the file runs in the sandbox without extra installs.)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# 1. FEATURE SCHEMA  --  the HRRR synoptic predictors, in priority order
# ---------------------------------------------------------------------------
# These names must match the keys in the per-event-hour feature dicts you build
# from herbie. Ordered by expected importance (see the earlier feature sketch).
# Start with a SMALL subset; adding features faster than you add events is how
# you overfit. The `DEFAULT_FEATURES` list is what the model actually uses --
# trim it to match what you can reliably pull.

ALL_FEATURES: List[str] = [
    "w700_speed_mph",      # 700 hPa wind speed over domain (primary driver)
    "w700_dir_sin",        # 700 hPa wind direction, sin component
    "w700_dir_cos",        # 700 hPa wind direction, cos component
    "mslp_grad",           # MSLP gradient magnitude across domain (pressure forcing)
    "z700_grad",           # 700 hPa geopotential-height gradient magnitude
    "lapse_rate",          # low-level lapse rate (stability)
    "froude_proxy",        # dimensionless mountain-height / Froude proxy
    "shear_700_850",       # cross-level shear magnitude 700-850 hPa
    "shear_700_500",       # cross-level shear magnitude 700-500 hPa
    "temp_adv_700",        # 700 hPa temperature advection (frontal signature)
    "bl_height",           # boundary-layer height
]

# Start here. Three predictors for the speed residual is already generous at
# small N. Expand only as events accumulate.
DEFAULT_FEATURES: List[str] = [
    "w700_speed_mph",
    "mslp_grad",
    "lapse_rate",
]

TARGETS: List[str] = ["delta_speed_mph", "delta_dir_sin", "delta_dir_cos"]


# ---------------------------------------------------------------------------
# 2. DATA TYPES
# ---------------------------------------------------------------------------

@dataclass
class Sample:
    """One event-hour: features + residual targets + provenance."""
    event: str                      # event id -> the LOEO grouping key
    features: Dict[str, float]
    delta_speed_mph: float
    delta_dir_sin: float
    delta_dir_cos: float
    # carried through for reconstruction / reporting:
    hrrr_prior_speed_mph: Optional[float] = None
    hrrr_prior_dir_deg: Optional[float] = None


def load_samples(records: Sequence[dict]) -> List[Sample]:
    """
    Build Samples from joined records. Each record must contain:
      - 'event'        : event id (string)
      - 'features'     : dict of HRRR feature_name -> value
      - the residual targets from as_label_dict():
        'delta_speed_mph', 'delta_dir_sin', 'delta_dir_cos'
      - optionally 'hrrr_prior_speed_mph', 'hrrr_prior_dir_deg'
    """
    samples: List[Sample] = []
    for r in records:
        samples.append(Sample(
            event=r["event"],
            features=r["features"],
            delta_speed_mph=float(r["delta_speed_mph"]),
            delta_dir_sin=float(r["delta_dir_sin"]),
            delta_dir_cos=float(r["delta_dir_cos"]),
            hrrr_prior_speed_mph=r.get("hrrr_prior_speed_mph"),
            hrrr_prior_dir_deg=r.get("hrrr_prior_dir_deg"),
        ))
    return samples


# ---------------------------------------------------------------------------
# 3. A MINIMAL STANDARDIZED RIDGE  (numpy only)
# ---------------------------------------------------------------------------
# Standardize features (zero mean / unit var) so the L2 penalty is fair across
# predictors, then closed-form ridge. One model per target. Standardization
# stats are learned on the TRAIN fold only and reused at predict time -- doing
# it globally would leak the held-out event.

class StandardizedRidge:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.mu_: Optional[np.ndarray] = None
        self.sd_: Optional[np.ndarray] = None
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "StandardizedRidge":
        self.mu_ = X.mean(axis=0)
        self.sd_ = X.std(axis=0)
        self.sd_[self.sd_ == 0] = 1.0           # guard constant columns
        Xs = (X - self.mu_) / self.sd_
        # center y so the intercept isn't penalized
        y_mean = y.mean()
        yc = y - y_mean
        n_feat = Xs.shape[1]
        A = Xs.T @ Xs + self.alpha * np.eye(n_feat)
        self.coef_ = np.linalg.solve(A, Xs.T @ yc)
        self.intercept_ = y_mean
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xs = (X - self.mu_) / self.sd_
        return Xs @ self.coef_ + self.intercept_


# ---------------------------------------------------------------------------
# 4. MATRIX ASSEMBLY
# ---------------------------------------------------------------------------

def to_matrix(samples: Sequence[Sample], features: Sequence[str]
              ) -> Tuple[np.ndarray, Dict[str, np.ndarray], List[str]]:
    """Return (X, {target_name: y_vector}, event_ids)."""
    X = np.array([[s.features[f] for f in features] for s in samples], dtype=float)
    Y = {
        "delta_speed_mph": np.array([s.delta_speed_mph for s in samples]),
        "delta_dir_sin":   np.array([s.delta_dir_sin for s in samples]),
        "delta_dir_cos":   np.array([s.delta_dir_cos for s in samples]),
    }
    events = [s.event for s in samples]
    return X, Y, events


# ---------------------------------------------------------------------------
# 5. METRICS  --  always vs the delta=0 baseline
# ---------------------------------------------------------------------------

def speed_rmse(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - true) ** 2)))


def dir_mae_deg(sin_p: np.ndarray, cos_p: np.ndarray,
                sin_t: np.ndarray, cos_t: np.ndarray) -> float:
    """Mean absolute angular error (deg) between predicted and true residual dir."""
    ang_p = np.arctan2(sin_p, cos_p)
    ang_t = np.arctan2(sin_t, cos_t)
    d = np.abs(ang_p - ang_t)
    d = np.minimum(d, 2 * math.pi - d)          # wrap to [0, pi]
    return float(np.degrees(np.mean(d)))


# ---------------------------------------------------------------------------
# 6. LEAVE-ONE-EVENT-OUT  (the only honest validation here)
# ---------------------------------------------------------------------------

@dataclass
class LOEOResult:
    n_events: int
    n_samples: int
    # speed residual, model vs baseline (delta=0):
    speed_rmse_model: float
    speed_rmse_baseline: float
    # direction residual, model vs baseline (no rotation = sin 0, cos 1):
    dir_mae_model: float
    dir_mae_baseline: float
    per_event: Dict[str, dict]

    def verdict(self, speed_margin: float = 0.5, dir_margin: float = 2.0) -> str:
        # Require a MEANINGFUL margin, not a hairline win. On scarce data a
        # sub-0.5 mph / sub-2 deg edge is within noise and must not count.
        s_better = self.speed_rmse_model < self.speed_rmse_baseline - speed_margin
        d_better = self.dir_mae_model < self.dir_mae_baseline - dir_margin
        if s_better and d_better:
            return ("SIGNAL: learned map beats raw-HRRR-as-BC on BOTH speed and "
                    "direction by a clear margin under LOEO. Worth expanding "
                    "features / events.")
        if s_better or d_better:
            return ("PARTIAL: clears the margin on one axis only. Possibly real "
                    "but weak; collect more events before trusting it.")
        return ("NO SIGNAL beyond baseline. Either the residual is noise, or the "
                "current features don't explain it. That gap is itself the "
                "finding -- revisit which synoptic features carry the terrain "
                "response (stability, pressure gradient) before adding capacity.")


def loeo(samples: Sequence[Sample],
         features: Sequence[str] = DEFAULT_FEATURES,
         alpha: float = 1.0) -> LOEOResult:
    """Hold out each event in turn; train on the rest; collect held-out preds."""
    events = sorted({s.event for s in samples})
    if len(events) < 2:
        raise ValueError(
            f"LOEO needs >= 2 events, got {len(events)}. With one event there is "
            "nothing to hold out. Add non-fire strong-wind events to grow N."
        )

    # accumulate held-out predictions across all folds
    sp_pred, sp_true = [], []
    ds_pred, dc_pred, ds_true, dc_true = [], [], [], []
    per_event: Dict[str, dict] = {}

    for held in events:
        train = [s for s in samples if s.event != held]
        test = [s for s in samples if s.event == held]

        Xtr, Ytr, _ = to_matrix(train, features)
        Xte, Yte, _ = to_matrix(test, features)

        # one ridge per target
        m_speed = StandardizedRidge(alpha).fit(Xtr, Ytr["delta_speed_mph"])
        m_sin = StandardizedRidge(alpha).fit(Xtr, Ytr["delta_dir_sin"])
        m_cos = StandardizedRidge(alpha).fit(Xtr, Ytr["delta_dir_cos"])

        p_speed = m_speed.predict(Xte)
        p_sin = m_sin.predict(Xte)
        p_cos = m_cos.predict(Xte)
        # renormalize (sin,cos) to unit circle
        norm = np.hypot(p_sin, p_cos)
        norm[norm == 0] = 1.0
        p_sin, p_cos = p_sin / norm, p_cos / norm

        sp_pred += list(p_speed); sp_true += list(Yte["delta_speed_mph"])
        ds_pred += list(p_sin);   dc_pred += list(p_cos)
        ds_true += list(Yte["delta_dir_sin"]); dc_true += list(Yte["delta_dir_cos"])

        per_event[held] = {
            "n_hours": len(test),
            "speed_rmse_model": speed_rmse(p_speed, Yte["delta_speed_mph"]),
            "speed_rmse_baseline": speed_rmse(
                np.zeros_like(Yte["delta_speed_mph"]), Yte["delta_speed_mph"]),
        }

    sp_pred = np.array(sp_pred); sp_true = np.array(sp_true)
    ds_pred = np.array(ds_pred); dc_pred = np.array(dc_pred)
    ds_true = np.array(ds_true); dc_true = np.array(dc_true)

    # baselines: speed delta=0 ; direction = no rotation (sin 0, cos 1)
    base_sin = np.zeros_like(ds_true)
    base_cos = np.ones_like(dc_true)

    return LOEOResult(
        n_events=len(events),
        n_samples=len(samples),
        speed_rmse_model=speed_rmse(sp_pred, sp_true),
        speed_rmse_baseline=speed_rmse(np.zeros_like(sp_true), sp_true),
        dir_mae_model=dir_mae_deg(ds_pred, dc_pred, ds_true, dc_true),
        dir_mae_baseline=dir_mae_deg(base_sin, base_cos, ds_true, dc_true),
        per_event=per_event,
    )


# ---------------------------------------------------------------------------
# 7. FINAL FIT + INFERENCE  (train on ALL events for deployment)
# ---------------------------------------------------------------------------

class BCResidualModel:
    """Deployable map: HRRR features -> predicted BC (speed, direction)."""

    def __init__(self, features: Sequence[str] = DEFAULT_FEATURES, alpha: float = 1.0):
        self.features = list(features)
        self.alpha = alpha
        self._speed = self._sin = self._cos = None

    def fit(self, samples: Sequence[Sample]) -> "BCResidualModel":
        X, Y, _ = to_matrix(samples, self.features)
        self._speed = StandardizedRidge(self.alpha).fit(X, Y["delta_speed_mph"])
        self._sin = StandardizedRidge(self.alpha).fit(X, Y["delta_dir_sin"])
        self._cos = StandardizedRidge(self.alpha).fit(X, Y["delta_dir_cos"])
        return self

    def predict_bc(self, features: Dict[str, float],
                   hrrr_prior_speed: float, hrrr_prior_dir: float
                   ) -> Tuple[float, float]:
        """Return (bc_speed_mph, bc_direction_deg) = prior + predicted residual."""
        x = np.array([[features[f] for f in self.features]], dtype=float)
        d_speed = float(self._speed.predict(x)[0])
        d_sin = float(self._sin.predict(x)[0])
        d_cos = float(self._cos.predict(x)[0])
        d_dir = math.degrees(math.atan2(d_sin, d_cos))
        bc_speed = max(0.0, hrrr_prior_speed + d_speed)
        bc_dir = (hrrr_prior_dir + d_dir) % 360.0
        return bc_speed, bc_dir


# ---------------------------------------------------------------------------
# 8. REPORTING
# ---------------------------------------------------------------------------

def print_loeo(res: LOEOResult) -> None:
    print("=" * 64)
    print(f"LEAVE-ONE-EVENT-OUT  ({res.n_events} events, {res.n_samples} event-hours)")
    print("=" * 64)
    print("\nSpeed residual (mph), lower is better:")
    print(f"  learned map : {res.speed_rmse_model:6.2f}")
    print(f"  baseline d=0: {res.speed_rmse_baseline:6.2f}  "
          f"({'beaten' if res.speed_rmse_model < res.speed_rmse_baseline else 'NOT beaten'})")
    print("\nDirection residual (deg MAE), lower is better:")
    print(f"  learned map : {res.dir_mae_model:6.2f}")
    print(f"  baseline    : {res.dir_mae_baseline:6.2f}  "
          f"({'beaten' if res.dir_mae_model < res.dir_mae_baseline else 'NOT beaten'})")
    print("\nPer held-out event (speed RMSE: model vs baseline):")
    for ev, d in res.per_event.items():
        flag = "ok " if d["speed_rmse_model"] < d["speed_rmse_baseline"] else "!! "
        print(f"  {flag}{ev:18s} {d['n_hours']:3d}h  "
              f"{d['speed_rmse_model']:6.2f} vs {d['speed_rmse_baseline']:6.2f}")
    print("\nVERDICT:")
    print("  " + res.verdict())


# ---------------------------------------------------------------------------
# 9. SYNTHETIC SELF-TEST  (delete once real labels exist)
# ---------------------------------------------------------------------------

def _make_synthetic(n_events: int = 6, hours_per_event: int = 8, seed: int = 0
                    ) -> List[dict]:
    """
    Plant a KNOWN linear relationship between features and the speed residual,
    add noise, and emit records in the exact format load_samples expects. A
    working trainer should beat the delta=0 baseline on this. Then we also emit
    a PURE-NOISE variant in __main__ to confirm the trainer honestly reports
    'no signal' when there is none -- guarding against a tool that always
    declares victory.
    """
    rng = np.random.default_rng(seed)
    records: List[dict] = []
    for e in range(n_events):
        prior_speed = float(rng.uniform(20, 45))
        prior_dir = float(rng.uniform(0, 360))
        for _h in range(hours_per_event):
            w700 = prior_speed + rng.normal(0, 3)
            mslp_grad = float(rng.uniform(0, 5))
            lapse = float(rng.uniform(4, 9))
            # planted truth: residual grows with pressure gradient & instability
            d_speed = 0.8 * mslp_grad + 0.5 * (lapse - 6.5) + rng.normal(0, 0.8)
            d_dir = 4.0 * (mslp_grad - 2.5) + rng.normal(0, 3)   # small dir nudge
            records.append({
                "event": f"event_{e:02d}",
                "features": {
                    "w700_speed_mph": w700,
                    "mslp_grad": mslp_grad,
                    "lapse_rate": lapse,
                },
                "delta_speed_mph": d_speed,
                "delta_dir_sin": math.sin(math.radians(d_dir)),
                "delta_dir_cos": math.cos(math.radians(d_dir)),
                "hrrr_prior_speed_mph": prior_speed,
                "hrrr_prior_dir_deg": prior_dir,
            })
    return records


def _make_noise(n_events: int = 6, hours_per_event: int = 8, seed: int = 1
               ) -> List[dict]:
    """Same shape, but residuals are pure noise -- no feature relationship."""
    rng = np.random.default_rng(seed)
    records: List[dict] = []
    for e in range(n_events):
        for _h in range(hours_per_event):
            d_dir = rng.normal(0, 20)
            records.append({
                "event": f"event_{e:02d}",
                "features": {
                    "w700_speed_mph": float(rng.uniform(20, 45)),
                    "mslp_grad": float(rng.uniform(0, 5)),
                    "lapse_rate": float(rng.uniform(4, 9)),
                },
                "delta_speed_mph": float(rng.normal(0, 3)),
                "delta_dir_sin": math.sin(math.radians(d_dir)),
                "delta_dir_cos": math.cos(math.radians(d_dir)),
                "hrrr_prior_speed_mph": 30.0,
                "hrrr_prior_dir_deg": 45.0,
            })
    return records


if __name__ == "__main__":
    print("TEST A -- planted linear signal (trainer SHOULD beat baseline)\n")
    samples = load_samples(_make_synthetic())
    res = loeo(samples, alpha=1.0)
    print_loeo(res)

    # demonstrate a deployable prediction
    model = BCResidualModel().fit(samples)
    feat = {"w700_speed_mph": 35.0, "mslp_grad": 4.0, "lapse_rate": 8.0}
    bc_s, bc_d = model.predict_bc(feat, hrrr_prior_speed=35.0, hrrr_prior_dir=45.0)
    print(f"\nDeployed prediction for a high-gradient/unstable hour:")
    print(f"  HRRR prior 35.0 mph @ 45deg  ->  BC {bc_s:.1f} mph @ {bc_d:.0f}deg")

    print("\n\nTEST B -- pure noise (trainer SHOULD report no signal)\n")
    res_noise = loeo(load_samples(_make_noise()), alpha=1.0)
    print_loeo(res_noise)
