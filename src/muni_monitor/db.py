"""SQLite schema (documented in SCHEMA.md) and connection helper."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "monitor.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS issuers(
  issuer_key TEXT PRIMARY KEY, name TEXT NOT NULL, pension_plans TEXT);
CREATE TABLE IF NOT EXISTS securities(
  cusip TEXT PRIMARY KEY, issuer_key TEXT NOT NULL REFERENCES issuers(issuer_key),
  description TEXT, coupon REAL NOT NULL, maturity_date TEXT NOT NULL,
  tax_exempt INTEGER NOT NULL, il_exempt INTEGER DEFAULT 0, is_callable INTEGER DEFAULT 0, call_date TEXT,
  source_doc_url TEXT);
CREATE TABLE IF NOT EXISTS trades(
  trade_id TEXT PRIMARY KEY, cusip TEXT NOT NULL REFERENCES securities(cusip),
  trade_date TEXT NOT NULL, trade_time TEXT, price REAL, yield REAL, par_amount REAL,
  trade_type TEXT, is_odd_lot INTEGER, is_interdealer INTEGER, is_outlier INTEGER,
  is_impossible_yield INTEGER);
CREATE TABLE IF NOT EXISTS treasury_curve(
  date TEXT NOT NULL, tenor_label TEXT NOT NULL, tenor_years REAL NOT NULL,
  par_yield_pct REAL, PRIMARY KEY(date, tenor_label));
CREATE TABLE IF NOT EXISTS pension_metrics(
  issuer_key TEXT NOT NULL, plan TEXT NOT NULL, fiscal_year INTEGER NOT NULL,
  funded_ratio_pct REAL, unfunded_liability REAL, employer_contribution REAL,
  source_url TEXT, PRIMARY KEY(issuer_key, plan, fiscal_year));
CREATE TABLE IF NOT EXISTS events(
  event_date TEXT NOT NULL, issuer_key TEXT, label TEXT NOT NULL, source TEXT,
  PRIMARY KEY(event_date, issuer_key, label));
CREATE TABLE IF NOT EXISTS trade_metrics(
  trade_id TEXT PRIMARY KEY, cusip TEXT, issuer_key TEXT, trade_date TEXT,
  years_to_maturity REAL, yield_pct REAL, treasury_yield_pct REAL, spread_bps REAL,
  muni_treasury_ratio REAL, modified_duration REAL, convexity REAL, dv01 REAL,
  bucket TEXT, tax_exempt INTEGER, il_exempt INTEGER, curve_date TEXT);
CREATE TABLE IF NOT EXISTS issuer_spread_series(
  issuer_key TEXT, date TEXT, median_spread_bps REAL, n_trades INTEGER,
  roll_mean_20 REAL, zscore_60 REAL, PRIMARY KEY(issuer_key, date));
CREATE TABLE IF NOT EXISTS stress_scores(
  issuer_key TEXT PRIMARY KEY, asof TEXT, spread_bps REAL, spread_change_bps REAL,
  funded_ratio_pct REAL, level_score REAL, change_score REAL, pension_score REAL,
  stress_score REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS dq_results(
  run_ts TEXT, check_name TEXT, severity TEXT, n_flagged INTEGER, n_total INTEGER,
  detail TEXT);
"""

ISSUERS = [
    ("IL_GO", "State of Illinois (General Obligation)", "SERS;TRS;SURS;JRS;GARS"),
    ("CHI_GO", "City of Chicago (General Obligation)", "MEABF;LABF;PABF;FABF"),
    ("CPS", "Chicago Public Schools / Board of Education", "CTPF;CPS-SERF"),
]


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT OR REPLACE INTO issuers VALUES (?,?,?)", ISSUERS)
    con.commit()
    return con
