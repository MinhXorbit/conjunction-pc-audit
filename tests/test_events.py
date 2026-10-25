import numpy as np
import pandas as pd
import pytest

from pc_audit.events import build_event_table, final_cdms


def _cdm(event, ttca, risk, **kw):
    row = {
        "event_id": event,
        "mission_id": kw.pop("mission_id", 1),
        "time_to_tca": ttca,
        "risk": risk,
        "max_risk_estimate": kw.pop("max_risk_estimate", risk + 1),
        "max_risk_scaling": kw.pop("max_risk_scaling", 2.0),
        "mahalanobis_distance": kw.pop("mahalanobis_distance", 3.0),
        "miss_distance": 1000.0,
        "relative_position_r": kw.pop("relative_position_r", 0.0),
        "t_sigma_r": 3.0,
        "c_sigma_r": 4.0,
        "t_sigma_t": 10.0,
        "c_sigma_t": 50.0,
        "t_sigma_n": 3.0,
        "c_sigma_n": 4.0,
        "c_object_type": kw.pop("c_object_type", "DEBRIS"),
        "c_rcs_estimate": kw.pop("c_rcs_estimate", 0.1),
        "relative_speed": 14000.0,
        "t_span": 5.0,
        "c_span": 2.0,
    }
    assert not kw
    return row


def _frame(rows):
    df = pd.DataFrame(rows)
    df["_pos"] = np.arange(len(df))
    return df


def test_decision_and_final_selection():
    df = _frame([_cdm(1, t, r) for t, r in zip([3.0, 2.0, 1.5, 0.8, 0.2], [-8, -7, -6, -5, -4.5])])
    ev = build_event_table(df, cutoff_days=1.0)
    row = ev.loc[1]
    assert row["time_to_tca_dec"] == 1.5 and row["risk_dec"] == -6
    assert row["time_to_tca_fin"] == 0.2 and row["risk_fin"] == -4.5
    assert bool(row["eligible"])


def test_alert_cutoff_two_days():
    df = _frame([_cdm(1, t, r) for t, r in zip([3.0, 2.0, 1.5, 0.8], [-8, -7, -6, -5])])
    ev = build_event_table(df, cutoff_days=2.0)
    assert ev.loc[1, "time_to_tca_dec"] == 2.0 and ev.loc[1, "risk_dec"] == -7


def test_no_later_cdm_is_ineligible():
    df = _frame([_cdm(2, 2.5, -9), _cdm(2, 1.2, -8)])
    ev = build_event_table(df, cutoff_days=1.0)
    assert not bool(ev.loc[2, "eligible"])


def test_event_without_decision_cdm_is_dropped():
    df = _frame([_cdm(3, 0.9, -9), _cdm(3, 0.5, -8)])
    ev = build_event_table(df, cutoff_days=1.0)
    assert 3 not in ev.index


def test_ties_resolve_to_last_row_in_file():
    df = _frame([_cdm(4, 2.0, -9), _cdm(4, 1.0, -8), _cdm(4, 1.0, -7)])
    ev = build_event_table(df, cutoff_days=1.0)
    assert ev.loc[4, "risk_dec"] == -7
    assert ev.loc[4, "risk_fin"] == -7
    assert not bool(ev.loc[4, "eligible"])


def test_negative_ttca_handling():
    df = _frame([_cdm(5, 2.0, -9), _cdm(5, 0.5, -8), _cdm(5, -0.1, -7)])
    assert final_cdms(df).loc[5, "time_to_tca"] == pytest.approx(-0.1)
    assert final_cdms(df, require_nonnegative_ttca=True).loc[5, "time_to_tca"] == pytest.approx(0.5)


def test_mission_id_carried():
    df = _frame([_cdm(6, 2.0, -9, mission_id=7), _cdm(6, 0.5, -8, mission_id=7)])
    ev = build_event_table(df, cutoff_days=1.0)
    assert ev.loc[6, "mission_id"] == 7
