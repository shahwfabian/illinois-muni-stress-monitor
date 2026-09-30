"""U.S. Treasury daily par yield curve (home.treasury.gov) and FRED cross-check."""
from __future__ import annotations

import io
import logging
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
       "daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve"
       "&field_tdr_date_value={y}&page&_format=csv")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
TENORS = {"1 Mo": 1 / 12, "1.5 Month": 1.5 / 12, "2 Mo": 2 / 12, "3 Mo": 0.25, "4 Mo": 4 / 12,
          "6 Mo": 0.5, "1 Yr": 1, "2 Yr": 2, "3 Yr": 3, "5 Yr": 5, "7 Yr": 7, "10 Yr": 10,
          "20 Yr": 20, "30 Yr": 30}
FRED_MAP = {"2 Yr": "DGS2", "10 Yr": "DGS10", "30 Yr": "DGS30"}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "muni-stress-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def parse_curve_csv(text: str) -> pd.DataFrame:
    """Wide Treasury CSV -> long (date, tenor_label, tenor_years, par_yield_pct)."""
    df = pd.read_csv(io.StringIO(text))
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
    cols = [c for c in df.columns if c in TENORS]
    long = df.melt(id_vars="Date", value_vars=cols, var_name="tenor_label", value_name="par_yield_pct")
    long["tenor_years"] = long["tenor_label"].map(TENORS)
    long = long.rename(columns={"Date": "date"}).dropna(subset=["par_yield_pct"])
    return long[["date", "tenor_label", "tenor_years", "par_yield_pct"]].drop_duplicates(["date", "tenor_label"])


def fetch_years(years: list[int], offline: bool = False) -> pd.DataFrame:
    """Download (or read cached) yearly CSVs. The current year is always refreshed online."""
    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for y in years:
        path = RAW / f"treasury_{y}.csv"
        if not offline and (y == date.today().year or not path.exists()):
            try:
                path.write_text(_get(URL.format(y=y)), encoding="utf-8")
            except Exception as e:  # network failure: fall back to cache
                log.warning("Treasury download %s failed (%s); using cache if present", y, e)
        if path.exists():
            frames.append(parse_curve_csv(path.read_text(encoding="utf-8")))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date", "tenor_label", "tenor_years", "par_yield_pct"])


def fred_cross_check(curve: pd.DataFrame, offline: bool = False) -> dict:
    """Compare Treasury.gov 2Y/10Y/30Y with FRED DGS series. Returns max abs diff in bp."""
    if offline:
        return {"status": "skipped", "detail": "offline"}
    out, worst, n = {}, 0.0, 0
    try:
        for label, sid in FRED_MAP.items():
            f = pd.read_csv(io.StringIO(_get(FRED.format(sid=sid))))
            f.columns = ["date", "fred"]
            f["fred"] = pd.to_numeric(f["fred"], errors="coerce")
            t = curve[curve.tenor_label == label][["date", "par_yield_pct"]]
            m = t.merge(f.dropna(), on="date")
            if m.empty:
                continue
            d = ((m.par_yield_pct - m.fred).abs() * 100).max()
            out[label] = round(float(d), 3)
            worst, n = max(worst, d), n + len(m)
        return {"status": "ok", "max_abs_diff_bp": round(float(worst), 3), "n_compared": n, "by_tenor": out}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
