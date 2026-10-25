"""Draw the figures from results/ (run scripts/run_audit.py first).

Static figures for print. Colors: two validated categorical slots
(blue #2a78d6, orange #eb6834) plus muted gray for de-emphasis.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"
FLOOR = -10.0

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "axes.linewidth": 0.8,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
    }
)


def log_ticks(ax, axis="x", lo=-10, hi=-2):
    ticks = list(range(lo, hi + 1, 2))
    labels = [f"$10^{{{t}}}$" for t in ticks]
    labels[0] = f"≤$10^{{{lo}}}$"
    if axis == "x":
        ax.set_xticks(ticks, labels)
    else:
        ax.set_yticks(ticks, labels)


def save(fig, outdir: pathlib.Path, name: str):
    fig.savefig(outdir / f"{name}.png", dpi=220, bbox_inches="tight")
    fig.savefig(outdir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------- Fig 1
def fig_decision_vs_final(ev: pd.DataFrame, outdir: pathlib.Path):
    e = ev[ev["eligible"]].copy()
    x = np.maximum(e["risk_dec"], FLOOR)
    y = np.maximum(e["risk_fin"], FLOOR)
    cons = np.maximum(e["risk_dec"], e["risk_fin"]) >= -6
    missed = (e["risk_dec"] < -5) & (e["risk_fin"] >= -5)
    rng = np.random.default_rng(1)
    jit = lambda n: rng.uniform(-0.12, 0.12, n)  # noqa: E731  (spread the pile at the floor only)
    xf = np.where(x <= FLOOR, x + jit(len(x)), x)
    yf = np.where(y <= FLOOR, y + jit(len(y)), y)

    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    ax.scatter(xf[~cons], yf[~cons], s=5, c=MUTED, alpha=0.25, lw=0, label="Other eligible events", rasterized=True)
    ax.scatter(xf[cons & ~missed], yf[cons & ~missed], s=12, c=BLUE, alpha=0.75, lw=0,
               label="Reached $10^{-6}$ at decision or final")
    ax.scatter(xf[missed], yf[missed], s=34, c=ORANGE, edgecolors=SURFACE, linewidths=1.2, zorder=5,
               label="Missed escalation at $10^{-5}$")
    lim = (-10.5, -1.0)
    ax.plot(lim, lim, color=AXIS, lw=0.8, zorder=1)
    ax.axvline(-5, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    ax.axhline(-5, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    log_ticks(ax, "x")
    log_ticks(ax, "y")
    ax.set_xlabel("Pc at ESA's final decision point (latest CDM ≥ 1 day before closest approach)")
    ax.set_ylabel("Pc in the last CDM")
    n_ab = int(((e["risk_dec"] >= -5) & (e["risk_fin"] >= -5)).sum())
    n_fa = int(((e["risk_dec"] >= -5) & (e["risk_fin"] < -5)).sum())
    ax.text(-9.9, -1.6, f"Below $10^{{-5}}$ at decision,\nabove it at the end: {int(missed.sum())}",
            fontsize=8, color=INK2, va="top")
    ax.text(-4.85, -9.6, f"Above $10^{{-5}}$ at decision,\nbelow it at the end: {n_fa}", fontsize=8, color=INK2)
    ax.text(-4.85, -1.6, f"Above at both: {n_ab}", fontsize=8, color=INK2, va="top")
    ax.text(-1.15, -5.15, "$10^{-5}$", fontsize=8, color=MUTED, ha="right", va="top")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=1, fontsize=8, handletextpad=0.3)
    save(fig, outdir, "fig1_decision_vs_final")


# --------------------------------------------------------------- Fig 2
def fig_change_distribution(ev1: pd.DataFrame, ev2: pd.DataFrame, outdir: pathlib.Path):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    bins = np.arange(-9.0, 8.5, 0.5)
    for ax, ev, title in (
        (axes[0], ev1, "Decision point (≥ 1 day before)"),
        (axes[1], ev2, "Alert point (≥ 2 days before)"),
    ):
        e = ev[ev["eligible"]]
        c = e[np.maximum(e["risk_dec"], e["risk_fin"]) >= -6]
        d = np.maximum(c["risk_fin"], FLOOR) - np.maximum(c["risk_dec"], FLOOR)
        w = np.full(len(d), 100.0 / len(d))
        ax.hist(d, bins=bins, weights=w, color=BLUE, rwidth=0.82)
        for v in (-1, 1):
            ax.axvline(v, color=MUTED, lw=0.9, ls=(0, (4, 3)))
        down = 100 * np.mean(d <= -1)
        up = 100 * np.mean(d >= 1)
        ax.text(-8.8, 0.97, f"Fell ≥10×\n{down:.1f}%", transform=ax.get_xaxis_transform(), fontsize=8, color=INK2, va="top")
        ax.text(7.9, 0.97, f"Rose ≥10×\n{up:.1f}%", transform=ax.get_xaxis_transform(), fontsize=8, color=INK2, va="top", ha="right")
        ax.set_title(f"{title}, n = {len(c)}", fontsize=9, color=INK, loc="left")
    fig.supxlabel(
        "Change in log$_{10}$ Pc, last CDM minus decision CDM (values below $10^{-10}$ counted at $10^{-10}$)",
        fontsize=9, color=INK2,
    )
    axes[0].set_ylabel("Share of events (%)")
    fig.tight_layout()
    save(fig, outdir, "fig2_change_distribution")


# --------------------------------------------------------------- Fig 3
def fig_policy_curve(curves: dict, outdir: pathlib.Path):
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    for key, color, label in (
        ("policy_curve_final_1e-5", BLUE, "Final Pc ≥ $10^{-5}$"),
        ("policy_curve_final_1e-4", ORANGE, "Final Pc ≥ $10^{-4}$"),
    ):
        c = pd.DataFrame(curves[key])
        final_above = c["both_above"] + c["missed_escalation"]
        alerts = c["both_above"] + c["false_alarm"]
        per = alerts / final_above
        ax.plot(per, 100 * c["sensitivity"], color=color, lw=1.6, marker="o", ms=3.2, label=label, zorder=3)
        same = np.isclose(c["threshold_decision"], c["threshold_final"])
        ax.scatter(per[same], 100 * c["sensitivity"][same], s=60, c=color, edgecolors=SURFACE, linewidths=1.5, zorder=4)
        i = int(np.flatnonzero(same)[0])
        offset = (-150, 14) if color == BLUE else (18, -34)
        ax.annotate(
            f"Same threshold at decision:\n{100 * c['sensitivity'][i]:.0f}% flagged, {per[i]:.1f} alerts per event",
            (per[i], 100 * c["sensitivity"][i]),
            xytext=offset, textcoords="offset points", fontsize=7.5, color=INK2,
            arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.8),
        )
    ax.set_xscale("log")
    ax.set_xlabel("Decision-time alerts per event that ends above the threshold (log scale)")
    ax.set_ylabel("Events ending above threshold\nflagged at decision (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower right", fontsize=8)
    save(fig, outdir, "fig3_policy_curve")


# --------------------------------------------------------------- Fig 4
def fig_radial(ev: pd.DataFrame, h4: dict, outdir: pathlib.Path):
    e = ev[ev["eligible"]]
    sig = np.sqrt(e["t_sigma_r_dec"] ** 2 + e["c_sigma_r_dec"] ** 2)
    z = ((e["relative_position_r_fin"] - e["relative_position_r_dec"]) / sig)
    z = z[np.isfinite(z) & (sig > 0)]

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw={"width_ratios": [1.35, 1]})
    edges = np.arange(-10, 10.25, 0.25)
    counts, _ = np.histogram(np.clip(z, -10, 10), bins=edges)
    centers = 0.5 * (edges[1:] + edges[:-1])
    a.bar(centers, counts, width=0.25 * 0.85, color=BLUE)
    g = len(z) * 0.25 * np.exp(-0.5 * centers**2) / math.sqrt(2 * math.pi)
    a.plot(centers, g, color=INK2, lw=1.0, ls=(0, (4, 3)), label="Gaussian, σ = 1 (most spread\nconsistent uncertainty allows)")
    a.set_yscale("log")
    a.set_ylim(0.8, counts.max() * 2)
    a.set_xlabel("Radial update / decision-time radial σ (values beyond ±10 at the edge)")
    a.set_ylabel("Events (log scale)")
    a.legend(loc="upper left", fontsize=7.5)

    order = ["DEBRIS", "UNKNOWN", "PAYLOAD", "ROCKET BODY"]
    bt = h4["by_object_type"]
    vals = [100 * bt[k]["frac_abs_gt_3"] for k in order] + [100 * h4["overall"]["frac_abs_gt_3"]]
    ns = [bt[k]["n"] for k in order] + [h4["overall"]["n"]]
    labels = ["Debris", "Unknown", "Payload", "Rocket\nbody", "All"]
    y = np.arange(len(labels))[::-1]
    b.barh(y, vals, height=0.55, color=BLUE)
    b.axvline(0.27, color=INK2, lw=1.0, ls=(0, (4, 3)))
    b.text(0.4, -0.75, "Gaussian bound 0.27%", fontsize=7.5, color=INK2, va="center")
    b.set_ylim(-1.1, len(labels) - 0.5)
    for yi, v, n in zip(y, vals, ns):
        b.text(v + 0.12, yi, f"{v:.1f}%  (n={n:,})", va="center", fontsize=7.5, color=INK2)
    b.set_yticks(y, labels)
    b.set_xlim(0, max(vals) * 1.75)
    b.set_xlabel("Updates beyond 3σ (%)")
    b.grid(axis="y", visible=False)
    save(fig, outdir, "fig4_radial_consistency")


# --------------------------------------------------------------- Fig S1
def fig_convention(sample: pd.DataFrame, outdir: pathlib.Path):
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    s = sample["max_risk_scaling"].clip(lower=1e-10)
    m = sample["mahalanobis_distance"].clip(lower=1e-3)
    ax.scatter(m, s, s=3, c=BLUE, alpha=0.3, lw=0, rasterized=True)
    ax.axhline(1.0, color=INK2, lw=0.9, ls=(0, (4, 3)))
    ax.axvline(math.sqrt(2), color=MUTED, lw=0.9, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Mahalanobis distance at closest approach (values below $10^{-3}$ shown at $10^{-3}$)")
    ax.set_ylabel("ESA max_risk_scaling")
    ax.text(1.6, 3e-9, "√2", color=MUTED, fontsize=8)
    ax.text(2e-3, 0.5, "Below this line: scaling < 1, dilution region", ha="left", va="top", fontsize=7.5, color=INK2)
    save(fig, outdir, "figS1_dilution_convention_check")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results")
    ap.add_argument("--figures", default="figures")
    args = ap.parse_args()
    rd, fd = pathlib.Path(args.results), pathlib.Path(args.figures)
    fd.mkdir(parents=True, exist_ok=True)
    res = json.load(open(rd / "results.json"))
    ev1 = pd.read_csv(rd / "events_decision_1day.csv", index_col=0)
    ev2 = pd.read_csv(rd / "events_alert_2day.csv", index_col=0)
    fig_decision_vs_final(ev1, fd)
    fig_change_distribution(ev1, ev2, fd)
    fig_policy_curve(res["primary_decision_1day"]["H2"], fd)
    fig_radial(ev1, res["primary_decision_1day"]["H4"], fd)
    fig_convention(pd.read_csv(rd / "cdm_sample_convention_check.csv"), fd)
    print("figures written to", fd)


if __name__ == "__main__":
    main()
