"""Unit tests use synthetic fixtures ONLY; nothing here is ever loaded into the real database."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from muni_monitor import etl, pipeline, quality, stress, treasury

CSV = ('Date,"1 Mo","2 Yr","10 Yr","30 Yr"\n'
       '09/29/2026,4.04,4.89,5.26,5.59\n09/28/2026,4.04,,5.24,5.56\n')


def test_parse_treasury_csv():
    df = treasury.parse_curve_csv(CSV)
    assert set(df.columns) == {"date", "tenor_label", "tenor_years", "par_yield_pct"}
    assert len(df) == 7  # blank cell dropped
    r = df[(df.date == "2026-09-29") & (df.tenor_label == "10 Yr")].iloc[0]
    assert r.par_yield_pct == 5.26 and r.tenor_years == 10


def _raw(**over):
    d = {"CUSIP": ["AAA"], "Trade Date": ["2025-01-02"], "Price(%)": ["101.5"], "Yield(%)": ["3.9"],
         "Par Traded": ["1,000,000"], "Trade Type": ["Sale to customer"]}
    d.update(over)
    return pd.DataFrame(d)


def test_normalize_trades():
    n = etl.normalize_trades(_raw())
    assert n.loc[0, "par_amount"] == 1_000_000 and n.loc[0, "trade_type"] == "SALE_TO_CUSTOMER"
    assert n.loc[0, "yield"] == 3.9


def test_normalize_trades_missing_column_raises():
    with pytest.raises(ValueError):
        etl.normalize_trades(_raw().drop(columns=["Yield(%)"]))


def test_flags():
    df = pd.DataFrame({"cusip": ["A"] * 6 + ["B"], "price": [100, 100.1, 99.9, 100, 100.05, 140, 100],
                       "par_amount": [1e6, 5e4, 1e6, 1e6, 1e6, 1e6, 1e6],
                       "yield": [4, 4, 4, 4, 0, 4, 20.0],
                       "trade_type": ["INTER_DEALER"] + ["SALE_TO_CUSTOMER"] * 6})
    f = etl.flag_trades(df)
    assert list(f.is_odd_lot) == [0, 1, 0, 0, 0, 0, 0]
    assert f.is_interdealer.iloc[0] == 1 and f.is_interdealer.sum() == 1
    assert list(f.is_impossible_yield) == [0, 0, 0, 0, 1, 0, 1]
    assert list(f.is_outlier) == [0, 0, 0, 0, 0, 1, 0]  # only the 140 price; B has <5 trades


def test_load_securities_percent_coupon(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("cusip,issuer_key,coupon,maturity_date,tax_exempt\naaa,IL_GO,5.0,2035-06-01,yes\n")
    s = etl.load_securities(p)
    assert s.loc[0, "coupon"] == 0.05 and s.loc[0, "tax_exempt"] == 1 and s.loc[0, "cusip"] == "AAA"


def test_quality_checks():
    raw = pd.DataFrame({"cusip": ["A", "A"], "trade_date": ["d"] * 2, "trade_time": ["t"] * 2,
                        "price": [1, 1], "yield": [1, np.nan], "par_amount": [1, 1], "trade_type": ["x"] * 2})
    assert quality.check_duplicates(raw)["n_flagged"] == 1
    assert quality.check_missing(raw)["n_flagged"] == 1
    assert quality.check_duplicates(raw.iloc[:0])["severity"] == "pass"
    t = pd.DataFrame({"cusip": ["A", "B"], "trade_date": ["2025-01-01", "2025-09-01"]})
    assert quality.check_stale(t)["n_flagged"] == 1


def test_settle_and_bucket():
    assert pipeline.settle_date(date(2025, 1, 2)) == date(2025, 1, 3)
    assert pipeline.settle_date(date(2024, 1, 2)) == date(2024, 1, 4)
    assert pipeline.bucket(2.9) == "0-3y" and pipeline.bucket(7.0) == "7-12y" and pipeline.bucket(20) == "12y+"


def test_compute_metrics_end_to_end_synthetic():
    curve = treasury.parse_curve_csv('Date,"1 Yr","10 Yr"\n01/02/2025,4.0,5.0\n')
    sec = pd.DataFrame({"cusip": ["AAA"], "issuer_key": ["IL_GO"], "coupon": [0.05],
                        "maturity_date": ["2030-01-03"], "tax_exempt": [1], "il_exempt": [0], "is_callable": [0]})
    tr = pd.DataFrame({"trade_id": ["1"], "cusip": ["AAA"], "trade_date": ["2025-01-02"], "yield_": [5.0],
                       "is_odd_lot": [0], "is_outlier": [0], "is_impossible_yield": [0]})
    m = pipeline.compute_metrics(tr, sec, curve)
    assert len(m) == 1
    r = m.iloc[0]
    # 5y maturity interpolated between 1y (4.0) and 10y (5.0): strictly between, spread positive/negative sane
    assert 4.0 < r.treasury_yield_pct < 5.0
    assert r.spread_bps == pytest.approx((5.0 - r.treasury_yield_pct) * 100)
    # a trade before any curve is unmatched
    tr["trade_date"] = "2024-06-01"
    assert pipeline.compute_metrics(tr, sec, curve).empty


def test_stress_components_and_reweighting():
    c = stress.component_scores(150, 0, 50)
    assert c == {"level": 50.0, "change": 50.0, "pension": 50.0}
    assert stress.composite(c)[0] == pytest.approx(50.0)
    c2 = stress.component_scores(300, None, None)
    score, note = stress.composite(c2)
    assert score == 100.0 and "change" in note and "pension" in note
    assert stress.component_scores(600, 80, 120) == {"level": 100.0, "change": 100.0, "pension": 0.0}


def test_issuer_series_zscore():
    m = pd.DataFrame({"issuer_key": "CPS", "trade_date": pd.date_range("2025-01-01", periods=30).strftime("%Y-%m-%d"),
                      "spread_bps": np.r_[np.full(29, 100.0) + np.arange(29) % 3, 300.0]})
    s = stress.issuer_series(m)
    assert s.zscore_60.iloc[-1] > 3 and len(s) == 30


def test_new_issue_trade_type_accepted():
    n = etl.normalize_trades(_raw(**{"Trade Type": ["NEW_ISSUE"]}))
    assert n.loc[0, "trade_type"] == "NEW_ISSUE"


def test_series_excludes_taxable_and_filters_bucket():
    m = pd.DataFrame({"issuer_key": "IL_GO", "trade_date": ["2024-01-01"] * 3,
                      "spread_bps": [-40.0, 80.0, 10.0], "tax_exempt": [1, 0, 1],
                      "bucket": ["7-12y", "7-12y", "0-3y"]})
    s = stress.issuer_series(m, "7-12y")
    assert len(s) == 1 and s.median_spread_bps.iloc[0] == -40.0 and s.n_trades.iloc[0] == 1


def test_callable_bonds_excluded_from_metrics():
    curve = treasury.parse_curve_csv('Date,"1 Yr","10 Yr"\n01/02/2025,4.0,5.0\n')
    sec = pd.DataFrame({"cusip": ["AAA"], "issuer_key": ["IL_GO"], "coupon": [0.05],
                        "maturity_date": ["2030-01-03"], "tax_exempt": [1], "il_exempt": [0], "is_callable": [1]})
    tr = pd.DataFrame({"trade_id": ["1"], "cusip": ["AAA"], "trade_date": ["2025-01-02"], "yield_": [5.0],
                       "is_odd_lot": [0], "is_outlier": [0], "is_impossible_yield": [0]})
    assert pipeline.compute_metrics(tr, sec, curve).empty
