"""Bootstrap confidence intervals: resampling events, or resampling missions."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def event_bootstrap(
    ev: pd.DataFrame, stat: Callable[[pd.DataFrame], float], n_boot: int, seed: int
) -> tuple[float, float]:
    """95% percentile interval from resampling event rows with replacement."""
    rng = np.random.default_rng(seed)
    n = len(ev)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[i] = stat(ev.iloc[idx])
    vals = vals[np.isfinite(vals)]
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def mission_bootstrap(
    ev: pd.DataFrame, stat: Callable[[pd.DataFrame], float], n_boot: int, seed: int, cluster: str = "mission_id"
) -> tuple[float, float]:
    """95% percentile interval from resampling whole missions with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in ev.groupby(cluster)}
    keys = np.array(list(groups.keys()))
    vals = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(keys, size=len(keys), replace=True)
        vals[i] = stat(pd.concat([groups[k] for k in pick]))
    vals = vals[np.isfinite(vals)]
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def fraction_bootstrap(flags: np.ndarray, n_boot: int, seed: int, chunk: int = 500) -> tuple[float, float]:
    """Fast event bootstrap for a mean of 0/1 flags."""
    flags = np.asarray(flags, dtype=float)
    n = flags.size
    if n == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    out = []
    done = 0
    while done < n_boot:
        b = min(chunk, n_boot - done)
        idx = rng.integers(0, n, (b, n))
        out.append(flags[idx].mean(axis=1))
        done += b
    vals = np.concatenate(out)
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))
