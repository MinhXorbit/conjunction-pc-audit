"""Metrics for each pre-registered hypothesis (see PLAN.md).

All risk values are ESA's log10 Pc. Thresholds are passed as probabilities
(for example 1e-5) and compared on the log10 scale.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

NEGLIGIBLE_FLOOR = -10.0
NOTIFICATION_LEVEL = -6.0
THRESHOLDS = (1e-4, 1e-5, 1e-6)


def clip_log_pc(r: pd.Series | np.ndarray) -> np.ndarray:
    """Set log10 Pc values below the negligible floor to the floor."""
    return np.maximum(np.asarray(r, dtype=float), NEGLIGIBLE_FLOOR)


# ---------------------------------------------------------------- H1
def consequential_mask(ev: pd.DataFrame) -> pd.Series:
    """Eligible events where either reading reached the 1e-6 notification level."""
    return ev["eligible"] & (np.maximum(ev["risk_dec"], ev["risk_fin"]) >= NOTIFICATION_LEVEL)


def delta_log_pc(ev: pd.DataFrame) -> np.ndarray:
    """Change in clipped log10 Pc from decision to final CDM."""
    return clip_log_pc(ev["risk_fin"]) - clip_log_pc(ev["risk_dec"])


def h1_instability(ev: pd.DataFrame) -> dict:
    sub = ev[consequential_mask(ev)]
    d = delta_log_pc(sub)
    n = len(sub)
    return {
        "n_consequential": int(n),
        "frac_abs_change_ge_1": float(np.mean(np.abs(d) >= 1)) if n else math.nan,
        "frac_abs_change_ge_2": float(np.mean(np.abs(d) >= 2)) if n else math.nan,
        "frac_up_ge_1": float(np.mean(d >= 1)) if n else math.nan,
        "frac_down_ge_1": float(np.mean(d <= -1)) if n else math.nan,
        "median_abs_change": float(np.median(np.abs(d))) if n else math.nan,
    }


# ---------------------------------------------------------------- H2
def confusion(ev: pd.DataFrame, threshold: float, dec_threshold: float | None = None) -> dict:
    """2x2 table of decision-time vs final classification against a threshold.

    ``dec_threshold`` lets the decision rule use a different threshold from the
    final classification (used for the policy curve).
    """
    e = ev[ev["eligible"]]
    lf = math.log10(threshold)
    ld = math.log10(dec_threshold if dec_threshold is not None else threshold)
    a = e["risk_dec"].to_numpy() >= ld
    b = e["risk_fin"].to_numpy() >= lf
    tp = int(np.sum(a & b))
    fn = int(np.sum(~a & b))  # missed escalation
    fp = int(np.sum(a & ~b))  # false alarm
    tn = int(np.sum(~a & ~b))
    return {
        "threshold_final": threshold,
        "threshold_decision": dec_threshold if dec_threshold is not None else threshold,
        "n_eligible": int(len(e)),
        "both_above": tp,
        "missed_escalation": fn,
        "false_alarm": fp,
        "both_below": tn,
        "sensitivity": tp / (tp + fn) if (tp + fn) else math.nan,
        "precision": tp / (tp + fp) if (tp + fp) else math.nan,
    }


def policy_curve(ev: pd.DataFrame, final_threshold: float, step_decades: float = 0.25) -> list[dict]:
    exps = np.arange(-3.0, -9.0 - 1e-9, -step_decades)
    return [confusion(ev, final_threshold, dec_threshold=10.0 ** x) for x in exps]


# ---------------------------------------------------------------- H3
def dilution_flag(scaling: pd.Series | np.ndarray, reciprocal: bool = False) -> np.ndarray:
    """True where the maximum attainable Pc is reached by shrinking the covariance."""
    s = np.asarray(scaling, dtype=float)
    return (s > 1.0) if reciprocal else (s < 1.0)


def h3a_convention_check(cdms: pd.DataFrame) -> dict:
    """Does scaling < 1 go with lower Mahalanobis distance than scaling > 1?"""
    s = cdms["max_risk_scaling"].to_numpy(dtype=float)
    m = cdms["mahalanobis_distance"].to_numpy(dtype=float)
    below, above, equal = s < 1.0, s > 1.0, s == 1.0
    med_below = float(np.median(m[below])) if below.any() else math.nan
    med_above = float(np.median(m[above])) if above.any() else math.nan
    near = m < math.sqrt(2.0)
    far = ~near
    res = {
        "n_cdms": int(len(s)),
        "n_scaling_below_1": int(below.sum()),
        "n_scaling_above_1": int(above.sum()),
        "n_scaling_equal_1": int(equal.sum()),
        "scaling_quantiles": {q: float(np.quantile(s, q)) for q in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99)},
        "median_mahalanobis_scaling_below_1": med_below,
        "median_mahalanobis_scaling_above_1": med_above,
        "frac_scaling_below_1_when_mahalanobis_below_sqrt2": float(np.mean(below[near])) if near.any() else math.nan,
        "frac_scaling_below_1_when_mahalanobis_above_sqrt2": float(np.mean(below[far])) if far.any() else math.nan,
    }
    if below.any() and above.any() and med_below < med_above:
        res["verdict"] = "pass"
    elif below.any() and above.any() and med_below > med_above:
        res["verdict"] = "inverted"
    else:
        res["verdict"] = "inconclusive"
    return res


def h3_dilution(ev: pd.DataFrame, reciprocal: bool = False) -> dict:
    e = ev[ev["eligible"]]
    dil = dilution_flag(e["max_risk_scaling_dec"], reciprocal)
    out = {"n_eligible": int(len(e)), "frac_decision_in_dilution": float(np.mean(dil))}
    for t in THRESHOLDS:
        lt = math.log10(t)
        below_dec = e["risk_dec"].to_numpy() < lt
        above_fin = e["risk_fin"].to_numpy() >= lt
        below_fin = ~above_fin
        missed = below_dec & above_fin
        stayed = below_dec & below_fin
        stayed_nonneg = stayed & (e["risk_dec"].to_numpy() >= NEGLIGIBLE_FLOOR)
        headroom_pool = dil & below_dec
        headroom = headroom_pool & (e["max_risk_estimate_dec"].to_numpy() >= lt)
        out[f"T={t:g}"] = {
            "frac_dilution_among_below_at_decision": float(np.mean(dil[below_dec])) if below_dec.any() else math.nan,
            "n_missed_escalation": int(missed.sum()),
            "frac_dilution_among_missed_escalations": float(np.mean(dil[missed])) if missed.any() else math.nan,
            "n_stayed_below": int(stayed.sum()),
            "frac_dilution_among_stayed_below": float(np.mean(dil[stayed])) if stayed.any() else math.nan,
            "n_stayed_below_nonnegligible": int(stayed_nonneg.sum()),
            "frac_dilution_among_stayed_below_nonnegligible": float(np.mean(dil[stayed_nonneg])) if stayed_nonneg.any() else math.nan,
            "n_dilution_below_at_decision": int(headroom_pool.sum()),
            "frac_headroom_max_risk_at_or_above_T": float(np.mean(headroom[headroom_pool])) if headroom_pool.any() else math.nan,
        }
    return out


# ---------------------------------------------------------------- H4
def radial_z(ev: pd.DataFrame) -> pd.Series:
    """Radial update normalized by the decision-time combined radial sigma."""
    e = ev[ev["eligible"]]
    sig = np.sqrt(e["t_sigma_r_dec"].astype(float) ** 2 + e["c_sigma_r_dec"].astype(float) ** 2)
    z = (e["relative_position_r_fin"].astype(float) - e["relative_position_r_dec"].astype(float)) / sig
    ok = np.isfinite(z) & (sig > 0)
    return z[ok]


def spread_summary(z: pd.Series | np.ndarray) -> dict:
    z = np.asarray(z, dtype=float)
    if z.size == 0:
        return {"n": 0}
    med = np.median(z)
    return {
        "n": int(z.size),
        "std": float(np.std(z, ddof=1)) if z.size > 1 else math.nan,
        "robust_spread_1p4826_mad": float(1.4826 * np.median(np.abs(z - med))),
        "median": float(med),
        "frac_abs_gt_3": float(np.mean(np.abs(z) > 3)),
        "frac_abs_gt_3_expected_gaussian": 0.0027,
    }


def h4_radial_consistency(ev: pd.DataFrame) -> dict:
    z = radial_z(ev)
    out = {"overall": spread_summary(z)}
    types = ev.loc[z.index, "c_object_type_dec"]
    out["by_object_type"] = {str(k): spread_summary(z[types == k]) for k in sorted(types.dropna().unique())}
    return out


# ---------------------------------------------------------------- H5
def rcs_terciles(ev: pd.DataFrame) -> pd.Series:
    e = ev[ev["eligible"]]
    rcs = e["c_rcs_estimate_dec"].astype(float)
    valid = rcs.dropna()
    q1, q2 = np.quantile(valid, [1 / 3, 2 / 3])
    lab = pd.Series(pd.NA, index=e.index, dtype="object")
    lab[rcs <= q1] = "small"
    lab[(rcs > q1) & (rcs <= q2)] = "medium"
    lab[rcs > q2] = "large"
    lab.attrs["cuts_m2"] = (float(q1), float(q2))
    return lab


def h5_by_group(ev: pd.DataFrame, groups: pd.Series, reciprocal: bool = False) -> dict:
    out = {}
    for g in [x for x in pd.unique(groups.dropna())]:
        idx = groups.index[groups == g]
        sub = ev.loc[idx]
        out[str(g)] = {
            "n_eligible": int(sub["eligible"].sum()),
            "h1": h1_instability(sub),
            "frac_decision_in_dilution": float(np.mean(dilution_flag(sub.loc[sub["eligible"], "max_risk_scaling_dec"], reciprocal)))
            if sub["eligible"].any()
            else math.nan,
            "h4": spread_summary(radial_z(sub)),
        }
    return out


# ---------------------------------------------------------------- Exploratory (added after results; see PLAN.md)
def policy_summary(curve: list[dict], targets=(0.9, 0.95)) -> dict:
    """Loosest decision threshold reaching each sensitivity target, and its alert load."""
    out = {}
    final_above = curve[0]["both_above"] + curve[0]["missed_escalation"]
    for tgt in targets:
        hit = [c for c in curve if c["sensitivity"] >= tgt]
        if not hit:
            out[f"sensitivity>={tgt:g}"] = None
            continue
        c = hit[0]  # curve runs from strict (1e-3) to loose (1e-9)
        alerts = c["both_above"] + c["false_alarm"]
        out[f"sensitivity>={tgt:g}"] = {
            "decision_threshold": c["threshold_decision"],
            "sensitivity": c["sensitivity"],
            "alerts": alerts,
            "events_ending_above": final_above,
            "alerts_per_event_ending_above": alerts / final_above if final_above else math.nan,
        }
    loosest = curve[-1]
    out["never_caught_even_at_1e-9"] = loosest["missed_escalation"]
    return out


def update_normalized_radial_z(ev: pd.DataFrame) -> pd.Series:
    """Radial update divided by sqrt(decision variance - final variance).

    Only defined where the combined radial uncertainty shrank. Under a
    consistent Gaussian update this statistic has unit spread.
    """
    e = ev[ev["eligible"]]
    vp = e["t_sigma_r_dec"].astype(float) ** 2 + e["c_sigma_r_dec"].astype(float) ** 2
    vf = e["t_sigma_r_fin"].astype(float) ** 2 + e["c_sigma_r_fin"].astype(float) ** 2
    shrank = (vp - vf) > 0
    dr = e["relative_position_r_fin"].astype(float) - e["relative_position_r_dec"].astype(float)
    z = dr[shrank] / np.sqrt((vp - vf)[shrank])
    return z[np.isfinite(z)]


def missed_escalation_cases(ev: pd.DataFrame, threshold: float) -> pd.DataFrame:
    e = ev[ev["eligible"]]
    lt = math.log10(threshold)
    m = e[(e["risk_dec"] < lt) & (e["risk_fin"] >= lt)]
    cols = [
        "mission_id", "c_object_type_dec", "time_to_tca_dec", "risk_dec",
        "time_to_tca_fin", "risk_fin", "max_risk_scaling_dec", "max_risk_estimate_dec",
    ]
    return m[cols].sort_values("risk_dec")


# ---------------------------------------------------------------- D1
def d1_expected_collisions(final: pd.DataFrame) -> dict:
    pc = 10.0 ** final["risk"].astype(float)
    out = {
        "n_events": int(len(final)),
        "sum_final_pc_expected_collisions": float(pc.sum()),
        "n_final_at_or_below_minus30": int((final["risk"] <= -30).sum()),
    }
    for t in THRESHOLDS:
        out[f"n_final_at_or_above_{t:g}"] = int((final["risk"] >= math.log10(t)).sum())
    return out
