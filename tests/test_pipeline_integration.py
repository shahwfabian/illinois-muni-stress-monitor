"""End-to-end pipeline run on SYNTHETIC CSVs in a temp dir (never touches the real database)."""
import sqlite3

import numpy as np
import pandas as pd

from muni_monitor import pipeline, treasury

CURVE = ('Date,"1 Yr","2 Yr","5 Yr","10 Yr","30 Yr"\n'
         + "".join(f"{d:%m/%d/%Y},4.0,4.2,4.5,4.8,5.2\n" for d in pd.bdate_range("2025-01-02", periods=80)))


def test_full_pipeline_idempotent(tmp_path, monkeypatch):
    manual, raw = tmp_path / "manual", tmp_path / "raw"
    manual.mkdir(), raw.mkdir()
    (raw / "treasury_2025.csv").write_text(CURVE)
    (manual / "securities.csv").write_text(
        "cusip,issuer_key,coupon,maturity_date,tax_exempt\nAAA111,IL_GO,5.0,2032-06-01,yes\n")
    (manual / "pension_metrics.csv").write_text(
        "issuer_key,plan,fiscal_year,funded_ratio_pct\nIL_GO,SERS,2024,45.0\n")
    dates = pd.bdate_range("2025-01-06", periods=40)
    rng = np.random.default_rng(0)
    rows = [f"AAA111,{d:%Y-%m-%d},10:00,{100 + rng.normal(0, .2):.3f},{4.9 + rng.normal(0, .03):.3f},1000000,Sale to customer"
            for d in dates]
    rows += [f"AAA111,{dates[0]:%Y-%m-%d},10:00,{100.0:.3f},4.9,1000000,Sale to customer"]  # exact-ish dup path
    rows += ["AAA111,2025-02-03,11:00,100.0,4.9,50000,Sale to customer",   # odd lot
             "ZZZ999,2025-02-03,11:00,100.0,4.9,1000000,Sale to customer"]  # unknown cusip
    (manual / "trades_test.csv").write_text("CUSIP,Trade Date,Trade Time,Price,Yield,Par Traded,Trade Type\n" + "\n".join(rows))

    monkeypatch.setattr(treasury, "RAW", raw)
    monkeypatch.setattr(treasury, "fred_cross_check", lambda c, o=False: {"status": "skipped"})
    kw = dict(offline=True, manual=manual, db_path=tmp_path / "t.db")
    s1 = pipeline.run(**kw)
    s2 = pipeline.run(**kw)
    assert s1 == s2
    assert s1["securities"] == 1 and s1["trade_metrics"] >= 38 and s1["issuers_scored"] == 1
    con = sqlite3.connect(tmp_path / "t.db")
    sc = con.execute("select spread_bps, funded_ratio_pct, stress_score from stress_scores").fetchone()
    assert sc[1] == 45.0 and 0 < sc[2] < 100
    assert con.execute("select count(*) from trades where is_odd_lot=1").fetchone()[0] == 1
    names = {r[0]: r for r in con.execute("select check_name, severity, n_flagged from dq_results")}
    assert names["unknown_cusip"][2] == 1 and names["odd_lot_trades"][2] == 1

