"""
mechanism_classifier.py
========================

Sorts each hindcast wind event into one of four PHYSICAL MECHANISMS, so the
Stormwatch pipeline knows -- per event -- how much WindNinja can be trusted and
which forecast axis (timing / speed / direction) is at risk.

    1. SYNOPTIC_TERRAIN   strong gradient flow channeled/accelerated by terrain
                          (gap winds, downslope windstorms, lee acceleration,
                          mountain waves). WindNinja's wheelhouse.
    2. PBL_TRANSIENT      a transition: cold-front wind shift, or low-level-jet
                          decoupling then morning mix-down. WindNinja can do
                          before/after snapshots, not the transition itself.
    3. CONVECTIVE_OUTFLOW thunderstorm downburst / derecho gust front.
                          NOT WindNinja, often not even reliably HRRR.
    4. FIRE_GENERATED     pyroconvection, plume collapse, indrafts. The fire
                          makes its own wind. Coupled-model (WRF-SFIRE) territory.

WHY rule-based, not ML
----------------------
N is tiny, the physics is known, and you need to TRUST and explain the bin.
A rule-based scorer is the right tool and doubles as the feature-extraction
spec for everything downstream. Each mechanism gets a score in [0,1] from the
diagnostics that are present; the classifier reports the argmax, the margin to
runner-up, a MIXED flag when the margin is small, and the list of diagnostics
that fired (the interpretability payload).

Honest-uncertainty design (matches the rest of the pipeline)
------------------------------------------------------------
* Missing diagnostics are skipped, not guessed -- a score is computed only over
  the evidence actually available, and `evidence_fraction` reports how much of
  each mechanism's signature could be evaluated. A confident label on 2 of 8
  diagnostics is not confident; the report shows that.
* Thresholds below are PHYSICALLY-MOTIVATED STARTING VALUES, not law. They are
  collected in THRESHOLDS for one-place calibration against your hindcast set,
  exactly like GUST_FACTOR in the label generator. Tune, don't trust blindly.

Data sources per diagnostic are noted inline (HRRR / sounding / MRMS / GOES /
RAWS) so this maps onto the P1 ingest tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# MECHANISM ENUM + WINDNINJA APPLICABILITY
# ---------------------------------------------------------------------------

class Mechanism(str, Enum):
    SYNOPTIC_TERRAIN = "synoptic_terrain"
    PBL_TRANSIENT = "pbl_transient"
    CONVECTIVE_OUTFLOW = "convective_outflow"
    FIRE_GENERATED = "fire_generated"


# How much the steady-state terrain solver can be trusted, per mechanism.
WINDNINJA_APPLICABILITY: Dict[Mechanism, str] = {
    Mechanism.SYNOPTIC_TERRAIN:   "HIGH  - core use case; downscale the sustained flow",
    Mechanism.PBL_TRANSIENT:      "PARTIAL - snapshot before & after the shift; cannot model the transition",
    Mechanism.CONVECTIVE_OUTFLOW: "NONE  - steady-state assumption invalid; out of scope",
    Mechanism.FIRE_GENERATED:     "NONE  - driver is the fire, not the synoptic state; needs coupled model",
}

# Which forecast axis each mechanism most threatens (for the bust decomposition).
PRIMARY_BUST_AXIS: Dict[Mechanism, str] = {
    Mechanism.SYNOPTIC_TERRAIN:   "speed (terrain amplification under-resolved by 3km input)",
    Mechanism.PBL_TRANSIENT:      "timing + direction (when the shift arrives, and the veer)",
    Mechanism.CONVECTIVE_OUTFLOW: "timing + speed (sudden localized gust)",
    Mechanism.FIRE_GENERATED:     "all axes (uncoupled forecast has no information)",
}


# ---------------------------------------------------------------------------
# CALIBRATABLE THRESHOLDS  (edit here; tune against the hindcast library)
# ---------------------------------------------------------------------------

THRESHOLDS = {
    # --- mid-level forcing (HRRR 700 hPa) ---
    "w700_strong_ms": 15.0,        # m/s; above this, synoptic flow is a real driver
    "w700_weak_ms": 8.0,           # m/s; below this, ambient forcing is weak (fire suspect)
    # --- pressure forcing (HRRR) ---
    "pgf_strong": 1.0,             # normalized gradient units; strong synoptic gradient
    # --- convection (MRMS / HRRR) ---
    "refl_convective_dbz": 35.0,   # composite reflectivity flagging active convection
    "cape_convective": 500.0,      # J/kg; meaningful convective potential
    # --- stability / downslope-windstorm setup (sounding or HRRR profile) ---
    "stable_lapse_ckm": 6.0,       # degC/km; below dry-adiabatic => stable layer present
    # --- temporal transition (RAWS time series within event window) ---
    "wind_shift_deg": 40.0,        # direction change marking a transition
    "shift_window_min": 90.0,      # minutes; shift faster than this = transient, not regime
    "temp_drop_front_c": 3.0,      # degC drop marking a frontal passage
    "pres_rise_front_hpa": 1.0,    # hPa rise behind a front
    # --- downburst (RAWS) ---
    "gust_spike_factor": 1.8,      # peak/sustained ratio suggesting a downburst blast
    "downburst_duration_min": 30.0,# brief localized blast
    # --- satellite plume (GOES) ---
    "pyrocb_ctt_c": -40.0,         # cloud-top temp colder than this over the fire = deep pyro plume
    # --- classification margin ---
    "mixed_margin": 0.20,          # if top score - runner-up < this => MIXED
    "min_evidence_fraction": 0.34, # below this evaluable evidence => LOW_CONFIDENCE
}


# ---------------------------------------------------------------------------
# EVENT DIAGNOSTICS  (one per event-window; all fields Optional -> graceful)
# ---------------------------------------------------------------------------

@dataclass
class EventDiagnostics:
    """
    Physical diagnostics for one hindcast event window. Populate what you have;
    leave the rest None. Each field notes its data source.
    """
    # --- synoptic forcing (HRRR / HRRRCast) ---
    w700_speed_ms: Optional[float] = None        # 700 hPa wind speed over domain
    pgf_norm: Optional[float] = None             # normalized MSLP/height gradient magnitude
    cross_ridge_flow: Optional[bool] = None      # flow has substantial across-barrier component
    forcing_sustained: Optional[bool] = None     # synoptic forcing steady over the window

    # --- stability / mountain-wave setup (sounding or HRRR pseudo-sounding) ---
    low_level_lapse_ckm: Optional[float] = None  # degC/km in lowest ~2 km
    critical_level: Optional[bool] = None        # wind reversal / strong dir shear aloft

    # --- convection (MRMS reflectivity, HRRR CAPE, lightning) ---
    max_reflectivity_dbz: Optional[float] = None
    max_cape: Optional[float] = None
    lightning_present: Optional[bool] = None

    # --- temporal transition (RAWS time series in the window) ---
    wind_shift_deg: Optional[float] = None       # max direction change across window
    shift_duration_min: Optional[float] = None   # how fast the shift happened
    temp_drop_c: Optional[float] = None          # coincident temperature drop (frontal)
    pres_rise_hpa: Optional[float] = None         # coincident pressure rise (frontal)
    shift_near_sunrise: Optional[bool] = None    # diurnal phase (LLJ mix-down signature)

    # --- downburst signature (RAWS) ---
    gust_to_sustained: Optional[float] = None    # peak gust / sustained ratio
    blast_duration_min: Optional[float] = None   # duration of the wind maximum

    # --- fire-generated (GOES + exclusion) ---
    goes_cloud_top_c: Optional[float] = None     # min cloud-top temp over the fire
    plume_collocated_with_fire: Optional[bool] = None  # plume sits over the fire, absent upstream
    local_wind_violent: Optional[bool] = None    # local gusts high despite the ambient state

    # provenance
    event_id: str = "unnamed_event"


# ---------------------------------------------------------------------------
# SCORING  --  each mechanism accumulates supportive / evaluable evidence
# ---------------------------------------------------------------------------

@dataclass
class _Tally:
    supportive: float = 0.0      # weighted indicators that FIRED for this mechanism
    evaluable: float = 0.0       # weighted indicators that COULD be evaluated
    reasons: List[str] = field(default_factory=list)

    def add(self, weight: float, value: Optional[bool], reason_if_true: str):
        """Record one indicator. None value = not evaluable (skipped, not guessed)."""
        if value is None:
            return
        self.evaluable += weight
        if value:
            self.supportive += weight
            self.reasons.append(reason_if_true)

    def score(self) -> float:
        return self.supportive / self.evaluable if self.evaluable > 0 else 0.0


@dataclass
class MechanismResult:
    primary: Optional[Mechanism]
    scores: Dict[Mechanism, float]
    evidence_fraction: Dict[Mechanism, float]
    margin: float
    mixed: bool
    low_confidence: bool
    reasons: Dict[Mechanism, List[str]]
    windninja_applicability: Optional[str]
    primary_bust_axis: Optional[str]

    def summary(self) -> str:
        if self.primary is None:
            return "UNCLASSIFIABLE - insufficient diagnostics"
        tag = self.primary.value.upper()
        flags = []
        if self.mixed:
            flags.append("MIXED")
        if self.low_confidence:
            flags.append("LOW_CONFIDENCE")
        flagstr = f"  [{', '.join(flags)}]" if flags else ""
        return f"{tag}{flagstr}"


def classify(d: EventDiagnostics, thr: dict = THRESHOLDS) -> MechanismResult:
    t = {m: _Tally() for m in Mechanism}

    # ---- helper to test a threshold only when the datum exists ----
    def ge(x, k):  # x >= threshold[k], or None if x is None
        return None if x is None else x >= thr[k]
    def le(x, k):
        return None if x is None else x <= thr[k]

    # convection present? used by several branches
    refl_conv = ge(d.max_reflectivity_dbz, "refl_convective_dbz")
    cape_conv = ge(d.max_cape, "cape_convective")
    # treat convection as present if EITHER strong refl or (cape AND lightning)
    convection_present: Optional[bool]
    parts = [p for p in (refl_conv, cape_conv, d.lightning_present) if p is not None]
    convection_present = (any([refl_conv, (cape_conv and d.lightning_present)])
                          if parts else None)

    # ---------------- 1. SYNOPTIC_TERRAIN ----------------
    st = t[Mechanism.SYNOPTIC_TERRAIN]
    st.add(2.0, ge(d.w700_speed_ms, "w700_strong_ms"), "strong 700hPa flow (driver present)")
    st.add(1.5, ge(d.pgf_norm, "pgf_strong"), "strong pressure-gradient forcing")
    st.add(1.0, d.cross_ridge_flow, "substantial cross-barrier flow component")
    st.add(1.5, d.forcing_sustained, "forcing sustained over window (regime, not transient)")
    st.add(1.5, le(d.low_level_lapse_ckm, "stable_lapse_ckm"),
           "stable low-level layer (downslope/mountain-wave setup)")
    st.add(1.0, d.critical_level, "critical level / strong directional shear aloft")
    # convection ARGUES AGAINST a clean synoptic-terrain regime
    if convection_present is not None:
        st.add(1.5, (not convection_present), "no active convection (clean terrain regime)")

    # ---------------- 2. PBL_TRANSIENT ----------------
    pt = t[Mechanism.PBL_TRANSIENT]
    shift_fast = None
    if d.wind_shift_deg is not None and d.shift_duration_min is not None:
        shift_fast = (d.wind_shift_deg >= thr["wind_shift_deg"]
                      and d.shift_duration_min <= thr["shift_window_min"])
    pt.add(2.0, shift_fast, "marked wind shift over a short window (transition)")
    # frontal thermodynamic signature
    frontal = None
    if d.temp_drop_c is not None and d.pres_rise_hpa is not None:
        frontal = (d.temp_drop_c >= thr["temp_drop_front_c"]
                   and d.pres_rise_hpa >= thr["pres_rise_front_hpa"])
    pt.add(2.0, frontal, "frontal signature (temp drop + pressure rise with shift)")
    pt.add(1.5, d.shift_near_sunrise, "shift near sunrise (LLJ decoupling / mix-down)")
    if convection_present is not None:
        pt.add(1.0, (not convection_present), "shift not driven by convection")

    # ---------------- 3. CONVECTIVE_OUTFLOW ----------------
    # Physical subtlety: pyroconvection IS convection. If the plume is
    # collocated with the fire, the reflectivity/CAPE/lightning are the FIRE's
    # own convection and must not also count as an independent ambient storm.
    # Gate the shared convective indicators on the plume NOT being fire-driven.
    co = t[Mechanism.CONVECTIVE_OUTFLOW]
    conv_is_ambient = (None if d.plume_collocated_with_fire is None
                       else (not d.plume_collocated_with_fire))

    def ambient_and(ind):
        # indicator counts for ambient convection only if not fire-collocated
        if ind is None:
            return None
        if conv_is_ambient is None:
            return ind                      # unknown collocation -> take at face value
        return ind and conv_is_ambient

    co.add(2.5, ambient_and(refl_conv), "high composite reflectivity (ambient convection)")
    co.add(1.5, ambient_and(cape_conv), "convective potential present (CAPE)")
    co.add(1.0, ambient_and(d.lightning_present), "lightning present")
    downburst = None
    if d.gust_to_sustained is not None and d.blast_duration_min is not None:
        downburst = (d.gust_to_sustained >= thr["gust_spike_factor"]
                     and d.blast_duration_min <= thr["downburst_duration_min"])
    co.add(2.0, ambient_and(downburst), "brief gust spike (downburst blast signature)")

    # ---------------- 4. FIRE_GENERATED ----------------
    fg = t[Mechanism.FIRE_GENERATED]
    fg.add(2.5, le(d.goes_cloud_top_c, "pyrocb_ctt_c"),
           "cold cloud top over fire (deep pyro-convective plume)")
    fg.add(2.0, d.plume_collocated_with_fire, "plume collocated with fire, absent upstream")
    # the exclusion signature: violent local wind under WEAK ambient forcing
    weak_ambient = le(d.w700_speed_ms, "w700_weak_ms")
    fire_excl = None
    if weak_ambient is not None and d.local_wind_violent is not None:
        fire_excl = (weak_ambient and d.local_wind_violent)
    fg.add(2.0, fire_excl, "violent local wind despite weak ambient forcing (fire-driven)")

    # ---------------- assemble ----------------
    scores = {m: t[m].score() for m in Mechanism}
    evidence = {
        m: (t[m].evaluable / _max_weight(m)) if _max_weight(m) > 0 else 0.0
        for m in Mechanism
    }
    reasons = {m: t[m].reasons for m in Mechanism}

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_m, top_s = ranked[0]
    second_s = ranked[1][1]
    margin = top_s - second_s

    # if literally nothing scored, unclassifiable
    if top_s == 0.0 and all(t[m].evaluable == 0 for m in Mechanism):
        return MechanismResult(None, scores, evidence, 0.0, False, True,
                               reasons, None, None)

    mixed = margin < thr["mixed_margin"]
    low_conf = evidence[top_m] < thr["min_evidence_fraction"]

    return MechanismResult(
        primary=top_m, scores=scores, evidence_fraction=evidence,
        margin=margin, mixed=mixed, low_confidence=low_conf, reasons=reasons,
        windninja_applicability=WINDNINJA_APPLICABILITY[top_m],
        primary_bust_axis=PRIMARY_BUST_AXIS[top_m],
    )


# max possible weight per mechanism (for evidence_fraction denominator)
_MAX_WEIGHTS = {
    Mechanism.SYNOPTIC_TERRAIN: 2.0 + 1.5 + 1.0 + 1.5 + 1.5 + 1.0 + 1.5,
    Mechanism.PBL_TRANSIENT: 2.0 + 2.0 + 1.5 + 1.0,
    Mechanism.CONVECTIVE_OUTFLOW: 2.5 + 1.5 + 1.0 + 2.0,
    Mechanism.FIRE_GENERATED: 2.5 + 2.0 + 2.0,
}
def _max_weight(m: Mechanism) -> float:
    return _MAX_WEIGHTS[m]


# ---------------------------------------------------------------------------
# REPORTING + HindcastEvent integration
# ---------------------------------------------------------------------------

def print_result(d: EventDiagnostics, r: MechanismResult) -> None:
    print(f"\n=== {d.event_id} ===")
    print(f"  -> {r.summary()}")
    if r.primary is None:
        return
    print(f"     WindNinja: {r.windninja_applicability}")
    print(f"     Bust axis: {r.primary_bust_axis}")
    print(f"     margin to runner-up: {r.margin:.2f}")
    print("     scores (evidence fraction):")
    for m in Mechanism:
        print(f"        {m.value:18s} {r.scores[m]:.2f}  ({r.evidence_fraction[m]:.0%} evaluable)")
    if r.reasons[r.primary]:
        print("     fired for primary:")
        for why in r.reasons[r.primary]:
            print(f"        - {why}")


def to_hindcast_block(r: MechanismResult) -> dict:
    """Attach to a HindcastEvent record (P2 schema)."""
    if r.primary is None:
        return {"mechanism": None, "classifiable": False}
    return {
        "mechanism": r.primary.value,
        "mechanism_scores": {m.value: round(s, 3) for m, s in r.scores.items()},
        "mixed": r.mixed,
        "low_confidence": r.low_confidence,
        "windninja_applicability": r.windninja_applicability.split(" - ")[0].strip(),
        "primary_bust_axis": r.primary_bust_axis,
        "evidence_fraction": {m.value: round(f, 3) for m, f in r.evidence_fraction.items()},
    }


# ---------------------------------------------------------------------------
# SELF-TEST  --  four archetype events you already know
# ---------------------------------------------------------------------------

def _archetypes() -> List[EventDiagnostics]:
    return [
        # Camp Fire 2018-11-08: strong NE gradient, dry, stable, no convection,
        # canyon channeling. Should be SYNOPTIC_TERRAIN.
        EventDiagnostics(
            event_id="camp_fire_2018 (expect SYNOPTIC_TERRAIN)",
            w700_speed_ms=18.0, pgf_norm=1.4, cross_ridge_flow=True,
            forcing_sustained=True, low_level_lapse_ckm=4.5, critical_level=True,
            max_reflectivity_dbz=5.0, max_cape=0.0, lightning_present=False,
            wind_shift_deg=10.0, shift_duration_min=600.0,
        ),
        # Missoula 2025-12-17 cold-frontal: synoptic but the danger is the
        # frontal SHIFT. Should be PBL_TRANSIENT.
        EventDiagnostics(
            event_id="missoula_dec2025_front (expect PBL_TRANSIENT)",
            w700_speed_ms=16.0, pgf_norm=1.1, cross_ridge_flow=True,
            forcing_sustained=False, low_level_lapse_ckm=6.5,
            max_reflectivity_dbz=15.0, max_cape=50.0, lightning_present=False,
            wind_shift_deg=70.0, shift_duration_min=45.0,
            temp_drop_c=6.0, pres_rise_hpa=2.5,
        ),
        # Missoula 2024-07 derecho: convective downdrafts, LSR 72-109 mph.
        # The event you correctly ruled out. Should be CONVECTIVE_OUTFLOW.
        EventDiagnostics(
            event_id="missoula_jul2024_derecho (expect CONVECTIVE_OUTFLOW)",
            w700_speed_ms=20.0, pgf_norm=0.8,
            max_reflectivity_dbz=60.0, max_cape=2000.0, lightning_present=True,
            gust_to_sustained=2.4, blast_duration_min=15.0,
            wind_shift_deg=50.0, shift_duration_min=20.0,
        ),
        # Generic plume-dominated blowup: weak ambient flow, deep pyroCb over
        # the fire, violent local winds. Should be FIRE_GENERATED.
        EventDiagnostics(
            event_id="plume_blowup (expect FIRE_GENERATED)",
            w700_speed_ms=6.0, pgf_norm=0.3, forcing_sustained=False,
            max_reflectivity_dbz=40.0, max_cape=800.0, lightning_present=True,
            goes_cloud_top_c=-55.0, plume_collocated_with_fire=True,
            local_wind_violent=True,
        ),
    ]


if __name__ == "__main__":
    print("MECHANISM CLASSIFIER SELF-TEST")
    print("=" * 64)
    import json
    for d in _archetypes():
        r = classify(d)
        print_result(d, r)
    print("\n\nExample HindcastEvent block (Camp Fire):")
    print(json.dumps(to_hindcast_block(classify(_archetypes()[0])), indent=2))
