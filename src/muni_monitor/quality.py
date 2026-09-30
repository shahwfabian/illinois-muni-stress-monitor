"""Data-quality checks. Each returns a dict row: check_name, severity, n_flagged, n_total, detail."""
from __future__ import annotations

import pandas as pd


def _r(name: str, sev: str, n: int, total: int, detail: str = "") -> dict:
    return {"check_name": name, "severity": "pass" if n == 0 else sev, "n_flagged": int(n),
            "n_total": int(total), "detail": detail}


def check_duplicates(raw_trades: pd.DataFrame) -> dict:
    key = ["cusip", "trade_date", "trade_time", "price", "par_amount", "trade_type"]
    n = int(raw_trades.duplicated(key).sum()) if len(raw_trades) else 0
    return _r("duplicate_trades", "warn", n, len(raw_trades), "exact duplicates removed on load")


def check_missing(raw_trades: pd.DataFrame) -> dict:
    need = ["cusip", "trade_date", "price", "yield", "par_amount", "trade_type"]
    n = int(raw_trades[need].isna().any(axis=1).sum()) if len(raw_trades) else 0
    return _r("missing_fields", "fail", n, len(raw_trades), "rows missing a required field are dropped")


def check_unknown_cusips(trades: pd.DataFrame, securities: pd.DataFrame) -> dict:
    n = int((~trades["cusip"].isin(securities["cusip"])).sum()) if len(trades) else 0
    return _r("unknown_cusip", "fail", n, len(trades), "trades whose CUSIP is not in securities.csv are dropped")


def check_impossible_yields(flagged: pd.DataFrame) -> dict:
    n = int(flagged["is_impossible_yield"].sum()) if len(flagged) else 0
    return _r("impossible_yields", "fail", n, len(flagged), "yield <=0 or >15% or missing; excluded from analytics")


def check_outliers(flagged: pd.DataFrame) -> list[dict]:
    if not len(flagged):
        return [_r("price_outliers", "warn", 0, 0), _r("odd_lot_trades", "info", 0, 0),
                _r("inter_dealer_trades", "info", 0, 0)]
    return [
        _r("price_outliers", "warn", flagged["is_outlier"].sum(), len(flagged),
           "per-CUSIP robust z (median/MAD) > 6; excluded from analytics"),
        _r("odd_lot_trades", "info", flagged["is_odd_lot"].sum(), len(flagged),
           "par < $100k; flagged and excluded from spread analytics"),
        _r("inter_dealer_trades", "info", flagged["is_interdealer"].sum(), len(flagged),
           "flagged; kept in analytics but separable"),
    ]


def check_stale(trades: pd.DataFrame, max_age_days: int = 90) -> dict:
    """CUSIPs whose most recent trade is older than max_age_days before the newest trade."""
    if not len(trades):
        return _r("stale_prices", "warn", 0, 0)
    last = pd.to_datetime(trades.groupby("cusip")["trade_date"].max())
    n = int(((last.max() - last).dt.days > max_age_days).sum())
    return _r("stale_prices", "warn", n, len(last), f"CUSIPs with last trade >{max_age_days}d before newest trade")


def check_date_alignment(metrics: pd.DataFrame, n_trades: int, max_gap_days: int = 5) -> dict:
    """Trades that could not be matched to a Treasury curve within max_gap_days."""
    n = n_trades - len(metrics)
    return _r("treasury_alignment", "warn", max(n, 0), n_trades,
              f"no curve on/before trade date within {max_gap_days}d, or maturity outside curve range")


def check_treasury(curve: pd.DataFrame, fred: dict) -> list[dict]:
    rows = []
    bad = int(((curve["par_yield_pct"] <= 0) | (curve["par_yield_pct"] > 20)).sum()) if len(curve) else 0
    rows.append(_r("treasury_yield_sanity", "fail", bad, len(curve), "par yields outside (0,20]%"))
    if fred.get("status") == "ok":
        d = fred["max_abs_diff_bp"]
        rows.append(_r("fred_cross_check", "warn", int(d > 1.0), fred["n_compared"],
                       f"max |Treasury.gov - FRED| = {d} bp over 2Y/10Y/30Y"))
    else:
        rows.append({"check_name": "fred_cross_check", "severity": "info", "n_flagged": 0,
                     "n_total": 0, "detail": f"{fred.get('status')}: {fred.get('detail', '')}"})
    return rows
