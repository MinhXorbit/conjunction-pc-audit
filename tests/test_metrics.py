import math

import numpy as np
import pandas as pd
import pytest

from pc_audit import metrics as M


def _ev(rows):
    """rows: (risk_dec, risk_fin, scaling_dec, maxrisk_dec, relpos_dec, relpos_fin, type)"""
    recs = []
    for i, (rd, rf, s, mx, pd_, pf, typ) in enumerate(rows):
        recs.append(
            {
                "event_id": i,
                "eligible": True,
                "risk_dec": rd,
                "risk_fin": rf,
                "max_risk_scaling_dec": s,
                "max_risk_estimate_dec": mx,
                "relative_position_r_dec": pd_,
                "relative_position_r_fin": pf,
                "t_sigma_r_dec": 3.0,
                "c_sigma_r_dec": 4.0,  # combined sigma = 5
                "c_object_type_dec": typ,
                "c_rcs_estimate_dec": 0.1 * (i + 1),
                "mission_id": 1,
            }
        )
    return pd.DataFrame(recs).set_index("event_id")


def test_clip_floor():
    assert list(M.clip_log_pc([-30, -12, -10, -4])) == [-10, -10, -10, -4]


def test_h1_counts_only_consequential_and_uses_clipping():
    ev = _ev(
        [
            (-30, -5.0, 2, -4, 0, 0, "DEBRIS"),  # consequential, delta = 5 after clipping
            (-6.0, -5.5, 2, -5, 0, 0, "DEBRIS"),  # consequential, delta 0.5
            (-7.0, -6.5, 2, -5, 0, 0, "DEBRIS"),  # not consequential (max -6.5 < -6)
            (-30, -20, 2, -15, 0, 0, "DEBRIS"),  # not consequential
        ]
    )
    h = M.h1_instability(ev)
    assert h["n_consequential"] == 2
    assert h["frac_abs_change_ge_1"] == pytest.approx(0.5)
    assert h["frac_up_ge_1"] == pytest.approx(0.5)
    assert h["frac_down_ge_1"] == 0.0


def test_confusion_cells():
    ev = _ev(
        [
            (-4.5, -3.5, 2, -3, 0, 0, "DEBRIS"),  # both above 1e-5
            (-6.0, -4.0, 2, -3, 0, 0, "DEBRIS"),  # missed escalation
            (-4.0, -7.0, 2, -3, 0, 0, "DEBRIS"),  # false alarm
            (-8.0, -9.0, 2, -7, 0, 0, "DEBRIS"),  # both below
        ]
    )
    c = M.confusion(ev, 1e-5)
    assert (c["both_above"], c["missed_escalation"], c["false_alarm"], c["both_below"]) == (1, 1, 1, 1)
    assert c["sensitivity"] == pytest.approx(0.5)
    assert c["precision"] == pytest.approx(0.5)


def test_threshold_boundary_is_inclusive():
    ev = _ev([(-5.0, -5.0, 2, -4, 0, 0, "DEBRIS")])
    c = M.confusion(ev, 1e-5)
    assert c["both_above"] == 1


def test_policy_curve_spans_range():
    ev = _ev([(-5.0, -4.0, 2, -4, 0, 0, "DEBRIS")])
    pc = M.policy_curve(ev, 1e-4)
    assert pc[0]["threshold_decision"] == pytest.approx(1e-3)
    assert pc[-1]["threshold_decision"] == pytest.approx(1e-9)


def test_dilution_flag_and_reciprocal():
    s = np.array([0.5, 1.0, 2.0])
    assert list(M.dilution_flag(s)) == [True, False, False]
    assert list(M.dilution_flag(s, reciprocal=True)) == [False, False, True]


def test_h3_missed_escalation_dilution_share():
    ev = _ev(
        [
            (-6.0, -4.0, 0.5, -3.0, 0, 0, "DEBRIS"),  # missed, dilution, headroom
            (-6.0, -4.0, 2.0, -5.5, 0, 0, "DEBRIS"),  # missed, robust
            (-8.0, -9.0, 0.5, -7.0, 0, 0, "DEBRIS"),  # stayed below, dilution, no headroom at 1e-5
        ]
    )
    h = M.h3_dilution(ev)["T=1e-05"]
    assert h["n_missed_escalation"] == 2
    assert h["frac_dilution_among_missed_escalations"] == pytest.approx(0.5)
    assert h["n_stayed_below"] == 1
    assert h["frac_headroom_max_risk_at_or_above_T"] == pytest.approx(0.5)


def test_radial_z_and_spread():
    ev = _ev(
        [
            (-6, -6, 2, -5, 0.0, 5.0, "DEBRIS"),  # z = 1
            (-6, -6, 2, -5, 0.0, -10.0, "PAYLOAD"),  # z = -2
            (-6, -6, 2, -5, 0.0, 20.0, "DEBRIS"),  # z = 4
        ]
    )
    z = M.radial_z(ev)
    assert list(np.round(z.to_numpy(), 6)) == [1.0, -2.0, 4.0]
    s = M.spread_summary(z)
    assert s["frac_abs_gt_3"] == pytest.approx(1 / 3)
    h4 = M.h4_radial_consistency(ev)
    assert h4["by_object_type"]["DEBRIS"]["n"] == 2


def test_policy_summary_picks_loosest_needed_threshold():
    curve = [
        {"threshold_decision": 1e-3, "sensitivity": 0.5, "both_above": 1, "missed_escalation": 1, "false_alarm": 0},
        {"threshold_decision": 1e-4, "sensitivity": 1.0, "both_above": 2, "missed_escalation": 0, "false_alarm": 4},
    ]
    s = M.policy_summary(curve, targets=(0.9,))
    assert s["sensitivity>=0.9"]["decision_threshold"] == 1e-4
    assert s["sensitivity>=0.9"]["alerts_per_event_ending_above"] == pytest.approx(3.0)
    assert s["never_caught_even_at_1e-9"] == 0


def test_update_normalized_z_only_where_uncertainty_shrank():
    ev = _ev([(-6, -6, 2, -5, 0.0, 4.0, "DEBRIS"), (-6, -6, 2, -5, 0.0, 4.0, "DEBRIS")])
    ev["t_sigma_r_fin"] = [0.0, 3.0]
    ev["c_sigma_r_fin"] = [3.0, 4.0]  # first: var 25 -> 9 (shrank by 16); second: unchanged
    z = M.update_normalized_radial_z(ev)
    assert len(z) == 1 and z.iloc[0] == pytest.approx(1.0)


def test_d1_expected_collisions():
    final = pd.DataFrame({"risk": [-4.0, -4.0, -30.0]})
    d = M.d1_expected_collisions(final)
    assert d["sum_final_pc_expected_collisions"] == pytest.approx(2e-4, rel=1e-6)
    assert d["n_final_at_or_above_0.0001"] == 2
    assert d["n_final_at_or_below_minus30"] == 1
