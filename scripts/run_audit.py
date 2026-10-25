"""Run every analysis in PLAN.md and write results/ (numbers) for the figures step.

Usage:
    python scripts/run_audit.py --data "data/raw/Collision Avoidance Challenge - Dataset/raw_data/raw_data_2015-2019.gz"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import platform
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pc_audit import __version__  # noqa: E402
from pc_audit import metrics as M  # noqa: E402
from pc_audit.bootstrap import fraction_bootstrap  # noqa: E402
from pc_audit.events import build_event_table, final_cdms, last_row_matches_min_ttca, load_raw  # noqa: E402

N_BOOT_EVENTS = 5000
N_BOOT_MISSIONS = 2000
SEED = 20261025


def sha256sum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------ bootstrap helpers
def mission_ratio_ci(num_by_m: pd.Series, den_by_m: pd.Series, n_boot: int, seed: int) -> tuple[float, float]:
    """Cluster bootstrap for a pooled ratio sum(num)/sum(den), resampling missions."""
    keys = den_by_m.index.to_numpy()
    num = num_by_m.reindex(keys).fillna(0).to_numpy(float)
    den = den_by_m.to_numpy(float)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(keys), (n_boot, len(keys)))
    n_s, d_s = num[picks].sum(1), den[picks].sum(1)
    vals = n_s[d_s > 0] / d_s[d_s > 0]
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def flag_cis(flags: pd.Series, missions: pd.Series, seed: int) -> dict:
    """Point estimate plus event and mission bootstrap intervals for a 0/1 flag."""
    f = flags.astype(float)
    if len(f) == 0:
        return {"estimate": math.nan, "n": 0}
    ev_lo, ev_hi = fraction_bootstrap(f.to_numpy(), N_BOOT_EVENTS, seed)
    num = f.groupby(missions).sum()
    den = f.groupby(missions).size()
    m_lo, m_hi = mission_ratio_ci(num, den, N_BOOT_MISSIONS, seed + 1)
    return {
        "estimate": float(f.mean()),
        "n": int(len(f)),
        "ci95_event_bootstrap": [ev_lo, ev_hi],
        "ci95_mission_bootstrap": [m_lo, m_hi],
    }


def std_cis(z: pd.Series, missions: pd.Series, seed: int) -> dict:
    """Spread of z with event and mission bootstrap intervals."""
    zz = z.to_numpy(float)
    rng = np.random.default_rng(seed)
    vals = []
    done = 0
    while done < N_BOOT_EVENTS:
        b = min(500, N_BOOT_EVENTS - done)
        idx = rng.integers(0, zz.size, (b, zz.size))
        vals.append(zz[idx].std(axis=1, ddof=1))
        done += b
    vals = np.concatenate(vals)
    # mission bootstrap on pooled moments
    g = pd.DataFrame({"z": zz, "m": missions.to_numpy()}).groupby("m")["z"]
    n_m, s1, s2 = g.size().to_numpy(float), g.sum().to_numpy(float), (g.apply(lambda x: (x**2).sum())).to_numpy(float)
    rng2 = np.random.default_rng(seed + 1)
    picks = rng2.integers(0, len(n_m), (N_BOOT_MISSIONS, len(n_m)))
    N, S1, S2 = n_m[picks].sum(1), s1[picks].sum(1), s2[picks].sum(1)
    var = (S2 - S1**2 / N) / (N - 1)
    mvals = np.sqrt(var[N > 1])
    return {
        "std": float(np.std(zz, ddof=1)),
        "n": int(zz.size),
        "ci95_event_bootstrap": [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))],
        "ci95_mission_bootstrap": [float(np.quantile(mvals, 0.025)), float(np.quantile(mvals, 0.975))],
    }


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


# ------------------------------------------------------------ main analysis
def analyse(ev: pd.DataFrame, cdms: pd.DataFrame, reciprocal: bool, seed: int) -> dict:
    e = ev[ev["eligible"]]
    res: dict = {"n_events_with_decision_cdm": int(len(ev)), "n_eligible": int(len(e))}

    # H1
    res["H1"] = M.h1_instability(ev)
    cons = e[M.consequential_mask(e)]
    d = M.delta_log_pc(cons)
    res["H1"]["ci_frac_abs_change_ge_1"] = flag_cis(pd.Series(np.abs(d) >= 1, index=cons.index), cons["mission_id"], seed)
    res["H1"]["ci_frac_abs_change_ge_2"] = flag_cis(pd.Series(np.abs(d) >= 2, index=cons.index), cons["mission_id"], seed + 10)

    # H2
    res["H2"] = {}
    for i, t in enumerate(M.THRESHOLDS):
        c = M.confusion(ev, t)
        lt = math.log10(t)
        above_fin = e[e["risk_fin"] >= lt]
        above_dec = e[e["risk_dec"] >= lt]
        # Share of final-above events that were below T at decision (1 - sensitivity)
        c["ci_missed_share_of_final_above"] = flag_cis(above_fin["risk_dec"] < lt, above_fin["mission_id"], seed + 20 + i)
        # Share of decision-above events that ended below T (1 - precision)
        c["ci_false_alarm_share_of_decision_above"] = flag_cis(above_dec["risk_fin"] < lt, above_dec["mission_id"], seed + 30 + i)
        res["H2"][f"T={t:g}"] = c
    res["H2"]["policy_curve_final_1e-4"] = M.policy_curve(ev, 1e-4)
    res["H2"]["policy_curve_final_1e-5"] = M.policy_curve(ev, 1e-5)

    # H3
    res["H3"] = {"convention_check": M.h3a_convention_check(cdms), "reciprocal_convention_used": reciprocal}
    res["H3"].update(M.h3_dilution(ev, reciprocal))
    dil = pd.Series(M.dilution_flag(e["max_risk_scaling_dec"], reciprocal), index=e.index)
    for i, t in enumerate(M.THRESHOLDS):
        lt = math.log10(t)
        missed = (e["risk_dec"] < lt) & (e["risk_fin"] >= lt)
        res["H3"][f"T={t:g}"]["ci_frac_dilution_among_missed"] = flag_cis(dil[missed], e.loc[missed, "mission_id"], seed + 40 + i)
    res["H3"]["ci_frac_decision_in_dilution"] = flag_cis(dil, e["mission_id"], seed + 50)

    # H4
    res["H4"] = M.h4_radial_consistency(ev)
    z = M.radial_z(ev)
    res["H4"]["ci_std"] = std_cis(z, ev.loc[z.index, "mission_id"], seed + 60)
    res["H4"]["ci_frac_abs_gt_3"] = flag_cis(pd.Series(np.abs(z) > 3, index=z.index), ev.loc[z.index, "mission_id"], seed + 70)

    # H5
    types = ev["c_object_type_dec"].where(ev["eligible"])
    res["H5"] = {"by_object_type": M.h5_by_group(ev, types, reciprocal)}
    terc = M.rcs_terciles(ev)
    res["H5"]["rcs_tercile_cuts_m2"] = list(terc.attrs["cuts_m2"])
    res["H5"]["n_eligible_with_rcs"] = int(terc.notna().sum())
    res["H5"]["by_rcs_tercile"] = M.h5_by_group(ev, terc, reciprocal)

    # Exploratory analyses added after the results were first seen (PLAN.md, changes section)
    zu = M.update_normalized_radial_z(ev)
    types_u = ev.loc[zu.index, "c_object_type_dec"]
    cases = M.missed_escalation_cases(ev, 1e-5)
    res["exploratory"] = {
        "policy_summary_final_1e-4": M.policy_summary(res["H2"]["policy_curve_final_1e-4"]),
        "policy_summary_final_1e-5": M.policy_summary(res["H2"]["policy_curve_final_1e-5"]),
        "update_normalized_radial_z": {
            "share_of_eligible_where_uncertainty_shrank": float(len(zu) / len(e)) if len(e) else math.nan,
            "overall": {**M.spread_summary(zu), "frac_abs_gt_5": float(np.mean(np.abs(zu) > 5)) if len(zu) else math.nan},
            "by_object_type": {str(k): M.spread_summary(zu[types_u == k]) for k in sorted(types_u.dropna().unique())},
        },
        "missed_escalations_at_1e-5": {
            "n": int(len(cases)),
            "n_decision_pc_below_1e-9": int((cases["risk_dec"] < -9).sum()),
            "n_decision_pc_below_1e-12": int((cases["risk_dec"] < -12).sum()),
            "cases": cases.reset_index().to_dict(orient="records"),
        },
    }

    # Per-mission breakdown
    pm = {}
    for mid, sub in ev.groupby("mission_id"):
        h1 = M.h1_instability(sub)
        zz = M.radial_z(sub)
        pm[str(mid)] = {
            "n_eligible": int(sub["eligible"].sum()),
            "n_consequential": h1["n_consequential"],
            "frac_abs_change_ge_1": h1["frac_abs_change_ge_1"],
            "radial_std": float(np.std(zz, ddof=1)) if len(zz) > 1 else None,
        }
    res["per_mission"] = pm
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True)
    ap.add_argument("--results", default="results")
    args = ap.parse_args()

    outdir = pathlib.Path(args.results)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_raw(args.data)
    final_all = final_cdms(df)

    conv = M.h3a_convention_check(df)
    reciprocal = conv["verdict"] == "inverted"

    ev1 = build_event_table(df, cutoff_days=1.0)
    ev2 = build_event_table(df, cutoff_days=2.0)
    ev1_nonneg = build_event_table(df, cutoff_days=1.0, require_nonnegative_final=True)

    results = {
        "meta": {
            "package_version": __version__,
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "data_file": pathlib.Path(args.data).name,
            "data_sha256": sha256sum(args.data),
            "n_cdms": int(len(df)),
            "n_events": int(df["event_id"].nunique()),
            "n_missions": int(df["mission_id"].nunique()),
            "share_events_last_row_is_min_ttca": last_row_matches_min_ttca(df),
            "n_boot_events": N_BOOT_EVENTS,
            "n_boot_missions": N_BOOT_MISSIONS,
            "seed": SEED,
        },
        "D1": M.d1_expected_collisions(final_all),
        "primary_decision_1day": analyse(ev1, df, reciprocal, SEED),
        "secondary_alert_2day": analyse(ev2, df, reciprocal, SEED + 1000),
        "robustness_final_nonnegative_ttca": {
            "H1": M.h1_instability(ev1_nonneg),
            "H2": {f"T={t:g}": M.confusion(ev1_nonneg, t) for t in M.THRESHOLDS},
            "H4": M.h4_radial_consistency(ev1_nonneg)["overall"],
        },
    }

    with open(outdir / "results.json", "w") as f:
        json.dump(to_jsonable(results), f, indent=2)

    # Compact tables for the figures step and for readers.
    rows = []
    for name in ("primary_decision_1day", "secondary_alert_2day"):
        for t in M.THRESHOLDS:
            c = results[name]["H2"][f"T={t:g}"]
            rows.append({"analysis": name, **{k: v for k, v in c.items() if not k.startswith("ci_")}})
    pd.DataFrame(rows).to_csv(outdir / "threshold_tables.csv", index=False)

    pc = []
    for tf in ("policy_curve_final_1e-4", "policy_curve_final_1e-5"):
        for r in results["primary_decision_1day"]["H2"][tf]:
            pc.append(r)
    pd.DataFrame(pc).to_csv(outdir / "policy_curve.csv", index=False)

    keep = [
        "mission_id", "eligible", "time_to_tca_dec", "time_to_tca_fin", "risk_dec", "risk_fin",
        "max_risk_scaling_dec", "max_risk_estimate_dec", "mahalanobis_distance_dec",
        "relative_position_r_dec", "relative_position_r_fin", "t_sigma_r_dec", "c_sigma_r_dec",
        "c_object_type_dec", "c_rcs_estimate_dec",
    ]
    ev1[keep].to_csv(outdir / "events_decision_1day.csv")
    ev2[keep].to_csv(outdir / "events_alert_2day.csv")
    # A small sample of CDMs for the convention-check figure (fixed seed).
    df[["max_risk_scaling", "mahalanobis_distance"]].sample(n=20000, random_state=SEED).to_csv(
        outdir / "cdm_sample_convention_check.csv", index=False
    )

    print(json.dumps(to_jsonable({"meta": results["meta"], "D1": results["D1"]}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
