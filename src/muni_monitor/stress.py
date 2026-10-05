"""Spread time series, rolling statistics and the transparent composite stress score.

Weights and anchors are documented and justified in METHODOLOGY.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

W_LEVEL, W_CHANGE, W_PENSION = 0.50, 0.20, 0.30
LEVEL_CAP_BPS = 300.0   # spread at/above this scores 100
CHANGE_CAP_BPS = 50.0   # +/- this change over the window maps to 100 / 0
CHANGE_WINDOW = 20      # observations
SERIES_BUCKET = "7-12y"  # fixed maturity bucket so the series is not distorted by maturity mix


def issuer_series(metrics: pd.DataFrame, bucket: str | None = None) -> pd.DataFrame:
    """Median spread per issuer/date (tax-exempt only; optional maturity bucket), 20-obs rolling
    mean and 60-obs z-score."""
    if bucket is not None and not metrics.empty:
        metrics = metrics[metrics["bucket"] == bucket]
    if "tax_exempt" in metrics.columns:  # nominal spreads of taxable and exempt bonds are not comparable
        metrics = metrics[metrics["tax_exempt"] == 1]
    if metrics.empty:
        return pd.DataFrame(columns=["issuer_key", "date", "median_spread_bps", "n_trades",
                                     "roll_mean_20", "zscore_60"])
    g = (metrics.groupby(["issuer_key", "trade_date"])["spread_bps"]
         .agg(median_spread_bps="median", n_trades="size").reset_index()
         .rename(columns={"trade_date": "date"}).sort_values(["issuer_key", "date"]))
    out = []
    for _, s in g.groupby("issuer_key"):
        s = s.copy()
        x = s["median_spread_bps"]
        s["roll_mean_20"] = x.rolling(20, min_periods=5).mean()
        mu, sd = x.rolling(60, min_periods=10).mean(), x.rolling(60, min_periods=10).std()
        s["zscore_60"] = (x - mu) / sd.replace(0, np.nan)
        out.append(s)
    return pd.concat(out, ignore_index=True)


def _clip01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


def component_scores(spread: float, change: float | None, funded_pct: float | None) -> dict:
    """Each component on 0-100 (higher = more stress); None if the input is unavailable."""
    return {
        "level": 100 * _clip01(spread / LEVEL_CAP_BPS),
        "change": None if change is None or np.isnan(change)
        else 100 * _clip01((change + CHANGE_CAP_BPS) / (2 * CHANGE_CAP_BPS)),
        "pension": None if funded_pct is None or np.isnan(funded_pct)
        else 100 * _clip01((100 - funded_pct) / 100),
    }


def composite(comp: dict) -> tuple[float, str]:
    """Weighted mean; if a component is missing its weight is redistributed pro rata and noted."""
    w = {"level": W_LEVEL, "change": W_CHANGE, "pension": W_PENSION}
    avail = {k: v for k, v in comp.items() if v is not None}
    tot = sum(w[k] for k in avail)
    score = sum(w[k] * v for k, v in avail.items()) / tot
    missing = [k for k in w if k not in avail]
    return float(score), ("missing components reweighted: " + ",".join(missing)) if missing else ""


def latest_scores(series: pd.DataFrame, pension: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k, s in series.groupby("issuer_key"):
        s = s.sort_values("date")
        spread = float(s["roll_mean_20"].iloc[-1]) if not np.isnan(s["roll_mean_20"].iloc[-1]) \
            else float(s["median_spread_bps"].tail(CHANGE_WINDOW).mean())
        change = None
        if len(s) > CHANGE_WINDOW:
            change = float(s["median_spread_bps"].iloc[-1] - s["median_spread_bps"].iloc[-1 - CHANGE_WINDOW])
        p = pension[pension.issuer_key == k].dropna(subset=["funded_ratio_pct"])
        funded = None
        if len(p):  # latest fiscal year, mean across plans (simple, unweighted)
            funded = float(p[p.fiscal_year == p.fiscal_year.max()]["funded_ratio_pct"].mean())
        comp = component_scores(spread, change, funded)
        score, note = composite(comp)
        rows.append({"issuer_key": k, "asof": s["date"].iloc[-1], "spread_bps": spread,
                     "spread_change_bps": change, "funded_ratio_pct": funded,
                     "level_score": comp["level"], "change_score": comp["change"],
                     "pension_score": comp["pension"], "stress_score": score, "notes": note})
    return pd.DataFrame(rows)
