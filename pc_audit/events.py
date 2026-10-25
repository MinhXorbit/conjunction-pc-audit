"""Event-level extraction: decision CDM, final CDM and eligibility.

Definitions follow PLAN.md:

- Final CDM: the last CDM of each event (smallest ``time_to_tca``; ties go
  to the row that appears last in the file), matching ESA's own definition
  of an event's final risk.
- Decision CDM: the latest CDM with ``time_to_tca >= cutoff`` (1.0 day is
  ESA's final decision point, 2.0 days its alert point).
- Eligible event: has a decision CDM and a final CDM that is a different,
  later CDM.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RAW_MEMBER = "Collision Avoidance Challenge - Dataset/raw_data/raw_data_2015-2019.gz"

# Columns carried from the CDM rows into the event table.
CARRY = [
    "time_to_tca",
    "risk",
    "max_risk_estimate",
    "max_risk_scaling",
    "mahalanobis_distance",
    "miss_distance",
    "relative_position_r",
    "t_sigma_r",
    "c_sigma_r",
    "t_sigma_t",
    "c_sigma_t",
    "t_sigma_n",
    "c_sigma_n",
    "c_object_type",
    "c_rcs_estimate",
    "relative_speed",
    "t_span",
    "c_span",
]


def load_raw(path: str) -> pd.DataFrame:
    """Load the raw CDM table and record each row's position in the file."""
    df = pd.read_csv(path, compression="infer", low_memory=False).copy()
    df["_pos"] = np.arange(len(df))
    return df


def _ordered(df: pd.DataFrame) -> pd.DataFrame:
    # Earliest CDM first; for equal time_to_tca, file order decides.
    return df.sort_values(
        ["event_id", "time_to_tca", "_pos"], ascending=[True, False, True], kind="mergesort"
    )


def final_cdms(df: pd.DataFrame, require_nonnegative_ttca: bool = False) -> pd.DataFrame:
    """Return one row per event: the final CDM."""
    d = df[df["time_to_tca"] >= 0] if require_nonnegative_ttca else df
    return _ordered(d).groupby("event_id", sort=True).tail(1).set_index("event_id")


def decision_cdms(df: pd.DataFrame, cutoff_days: float) -> pd.DataFrame:
    """Return one row per event that has a CDM at or before the decision point."""
    d = df[df["time_to_tca"] >= cutoff_days]
    return _ordered(d).groupby("event_id", sort=True).tail(1).set_index("event_id")


def build_event_table(
    df: pd.DataFrame, cutoff_days: float = 1.0, require_nonnegative_final: bool = False
) -> pd.DataFrame:
    """Pair each event's decision CDM with its final CDM.

    Returns all events that have a decision CDM. The ``eligible`` column marks
    events whose final CDM is a different, later CDM than the decision CDM.
    """
    fin = final_cdms(df, require_nonnegative_ttca=require_nonnegative_final)
    dec = decision_cdms(df, cutoff_days)

    mission = df.groupby("event_id")["mission_id"].first()

    dec_part = dec[CARRY + ["_pos"]].add_suffix("_dec")
    fin_part = fin[CARRY + ["_pos"]].add_suffix("_fin")
    ev = dec_part.join(fin_part, how="inner")
    ev["mission_id"] = mission.reindex(ev.index)

    ev["eligible"] = (ev["_pos_fin"] != ev["_pos_dec"]) & (ev["time_to_tca_fin"] < cutoff_days)
    ev["cutoff_days"] = cutoff_days
    return ev


def last_row_matches_min_ttca(df: pd.DataFrame) -> float:
    """Share of events whose last row in file order is also the minimum-ttca CDM."""
    last_in_file = df.groupby("event_id")["_pos"].max()
    fin = final_cdms(df)["_pos"]
    return float((last_in_file.reindex(fin.index) == fin).mean())
