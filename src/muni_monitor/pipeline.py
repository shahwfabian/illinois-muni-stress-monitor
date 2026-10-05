"""Single-command, idempotent pipeline:  python -m muni_monitor.pipeline [--offline]"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import analytics as an
from . import etl, quality, stress, treasury
from .db import connect

log = logging.getLogger("pipeline")
BUCKETS = [(0, 3, "0-3y"), (3, 7, "3-7y"), (7, 12, "7-12y"), (12, 100, "12y+")]
MAX_CURVE_GAP_DAYS = 5


def bucket(y: float) -> str:
    return next(label for lo, hi, label in BUCKETS if lo <= y < hi)


def settle_date(trade_date: date) -> date:
    """T+2 before 2024-05-28, T+1 after (SEC rule); business days, no holiday calendar."""
    n = 2 if trade_date < date(2024, 5, 28) else 1
    return (pd.Timestamp(trade_date) + pd.offsets.BDay(n)).date()


def curve_asof(curves: dict[str, pd.DataFrame], dates: list[str], d: str):
    i = np.searchsorted(dates, d, side="right") - 1
    if i < 0:
        return None
    if (pd.Timestamp(d) - pd.Timestamp(dates[i])).days > MAX_CURVE_GAP_DAYS:
        return None
    return dates[i], curves[dates[i]]


def compute_metrics(trades: pd.DataFrame, sec: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    """Per-trade analytics. Uses trades that are not odd-lot / outlier / impossible-yield."""
    use = trades[(trades.is_odd_lot == 0) & (trades.is_outlier == 0) & (trades.is_impossible_yield == 0)]
    if use.empty or curve.empty:
        return pd.DataFrame()
    curves = {d: g.sort_values("tenor_years") for d, g in curve.groupby("date")}
    dates = sorted(curves)
    secs = sec.set_index("cusip")
    rows = []
    for t in use.itertuples():
        s = secs.loc[t.cusip]
        td = date.fromisoformat(t.trade_date)
        mat = date.fromisoformat(s.maturity_date)
        st = settle_date(td)
        if mat <= st:
            continue
        found = curve_asof(curves, dates, t.trade_date)
        if found is None:
            continue
        cdate, c = found
        ytm = t.yield_ / 100
        yrs = (mat - st).days / 365.25
        ty = an.interpolate_curve(c.tenor_years.values, c.par_yield_pct.values, yrs)
        if np.isnan(ty):
            continue
        try:
            rm = an.risk_measures(st, mat, float(s.coupon), ytm)
        except Exception as e:  # pragma: no cover
            log.warning("risk calc failed for %s: %s", t.cusip, e)
            continue
        rows.append({
            "trade_id": t.trade_id, "cusip": t.cusip, "issuer_key": s.issuer_key,
            "trade_date": t.trade_date, "years_to_maturity": yrs, "yield_pct": ytm * 100,
            "treasury_yield_pct": ty, "spread_bps": an.spread_bps(ytm, ty / 100),
            "muni_treasury_ratio": an.muni_treasury_ratio(ytm, ty / 100),
            "modified_duration": rm["modified"], "convexity": rm["convexity"], "dv01": rm["dv01"],
            "bucket": bucket(yrs), "tax_exempt": int(s.tax_exempt), "curve_date": cdate})
    return pd.DataFrame(rows)


def replace_table(con, name: str, df: pd.DataFrame) -> None:
    con.execute(f"DELETE FROM {name}")
    if len(df):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})")]
        df.reindex(columns=cols).to_sql(name, con, if_exists="append", index=False)


def run(offline: bool = False, manual: Path | None = None, db_path: Path | None = None) -> dict:
    manual = manual or etl.MANUAL
    con = connect(db_path) if db_path else connect()
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dq: list[dict] = []

    # Treasury benchmark + FRED cross-check
    yrs = list(range(2023, date.today().year + 1))
    curve = treasury.fetch_years(yrs, offline=offline)
    replace_table(con, "treasury_curve", curve)
    dq += quality.check_treasury(curve, treasury.fred_cross_check(curve, offline))

    # Reference data (manual CSVs)
    sec = etl.load_securities(manual / "securities.csv")
    replace_table(con, "securities", sec)
    pen = etl.load_optional(manual / "pension_metrics.csv",
                            ["issuer_key", "plan", "fiscal_year", "funded_ratio_pct",
                             "unfunded_liability", "employer_contribution", "source_url"])
    replace_table(con, "pension_metrics", pen)
    ev = etl.load_optional(manual / "events.csv", ["event_date", "issuer_key", "label", "source"])
    replace_table(con, "events", ev)

    # Trades
    raw = etl.load_trades_files(manual)
    dq.append(quality.check_duplicates(raw))
    dq.append(quality.check_missing(raw))
    tr = raw.dropna(subset=["cusip", "trade_date", "price", "yield", "par_amount", "trade_type"])
    tr = tr.drop_duplicates(["cusip", "trade_date", "trade_time", "price", "par_amount", "trade_type"])
    dq.append(quality.check_unknown_cusips(tr, sec))
    tr = tr[tr.cusip.isin(sec.cusip)].reset_index(drop=True)
    if len(tr):
        tr["trade_id"] = tr.apply(etl.trade_id, axis=1)
    else:
        tr["trade_id"] = []
    flagged = etl.flag_trades(tr) if len(tr) else tr.assign(
        is_odd_lot=[], is_interdealer=[], is_impossible_yield=[], is_outlier=[])
    dq.append(quality.check_impossible_yields(flagged))
    dq += quality.check_outliers(flagged)
    dq.append(quality.check_stale(flagged))
    replace_table(con, "trades", flagged)

    # Analytics
    fl = flagged.rename(columns={"yield": "yield_"})
    metrics = compute_metrics(fl, sec, curve) if len(fl) else pd.DataFrame()
    n_eligible = int(((flagged.is_odd_lot == 0) & (flagged.is_outlier == 0)
                      & (flagged.is_impossible_yield == 0)).sum()) if len(flagged) else 0
    dq.append(quality.check_date_alignment(metrics, n_eligible))
    replace_table(con, "trade_metrics", metrics)

    series = stress.issuer_series(metrics)
    replace_table(con, "issuer_spread_series", series)
    scores = stress.latest_scores(series, pen) if len(series) else pd.DataFrame()
    replace_table(con, "stress_scores", scores)

    con.execute("DELETE FROM dq_results WHERE run_ts=?", (run_ts,))
    con.executemany("INSERT INTO dq_results VALUES (?,?,?,?,?,?)",
                    [(run_ts, d["check_name"], d["severity"], d["n_flagged"], d["n_total"], d["detail"]) for d in dq])
    con.commit()
    for d in dq:
        log.info("DQ %-22s %-5s flagged=%d/%d %s", d["check_name"], d["severity"], d["n_flagged"], d["n_total"], d["detail"])
    summary = {"treasury_rows": len(curve), "securities": len(sec), "trades": len(flagged),
               "trade_metrics": len(metrics), "issuers_scored": len(scores)}
    log.info("done: %s", summary)
    con.close()
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    run(ap.parse_args().offline)


if __name__ == "__main__":
    main()
