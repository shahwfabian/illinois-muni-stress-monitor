"""Extract/transform/load for manually supplied CSVs (securities, trades, pension, events).

EMMA prohibits automated access, so trades are ingested from CSVs the user downloads.
Every transform here is a pure function so it can be unit tested.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

MANUAL = Path(__file__).resolve().parents[2] / "data" / "manual"
ODD_LOT_PAR = 100_000  # par < $100k is treated as retail/odd-lot

# Header aliases -> normalized names. Verify against your actual EMMA export; unknown
# headers fail loudly rather than being guessed.
TRADE_ALIASES = {
    "cusip": "cusip", "trade date": "trade_date", "trade_date": "trade_date",
    "trade time": "trade_time", "trade_time": "trade_time", "price": "price", "price(%)": "price",
    "price (%)": "price", "yield": "yield", "yield(%)": "yield", "yield (%)": "yield",
    "par traded": "par_amount", "par_amount": "par_amount", "par amount": "par_amount",
    "trade type": "trade_type", "trade_type": "trade_type",
}
TRADE_REQUIRED = ["cusip", "trade_date", "price", "yield", "par_amount", "trade_type"]
TRADE_TYPES = {
    "sale to customer": "SALE_TO_CUSTOMER", "customer bought": "SALE_TO_CUSTOMER",
    "purchase from customer": "PURCHASE_FROM_CUSTOMER", "customer sold": "PURCHASE_FROM_CUSTOMER",
    "new_issue": "NEW_ISSUE", "inter-dealer": "INTER_DEALER", "interdealer": "INTER_DEALER", "inter dealer": "INTER_DEALER",
}


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[,$%\s]", "", regex=True), errors="coerce")


def normalize_trades(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename headers, parse types, standardise trade type. Raises on missing columns."""
    ren = {c: TRADE_ALIASES[c.strip().lower()] for c in raw.columns if c.strip().lower() in TRADE_ALIASES}
    df = raw.rename(columns=ren)
    missing = [c for c in TRADE_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"trade file missing columns {missing}; got {list(raw.columns)}")
    if "trade_time" not in df.columns:
        df["trade_time"] = ""
    out = pd.DataFrame({
        "cusip": df["cusip"].astype(str).str.strip().str.upper(),
        "trade_date": pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "trade_time": df["trade_time"].fillna("").astype(str),
        "price": _num(df["price"]), "yield": _num(df["yield"]), "par_amount": _num(df["par_amount"]),
        "trade_type": df["trade_type"].astype(str).str.strip().str.lower().map(TRADE_TYPES),
    })
    return out


def trade_id(row: pd.Series) -> str:
    key = "|".join(str(row[k]) for k in ["cusip", "trade_date", "trade_time", "price", "par_amount", "trade_type"])
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def flag_trades(df: pd.DataFrame, impossible_lo: float = 0.0, impossible_hi: float = 15.0,
                mad_k: float = 6.0) -> pd.DataFrame:
    """Add is_odd_lot, is_interdealer, is_impossible_yield and is_outlier (per-CUSIP robust
    z on price using median/MAD; needs >=5 trades per CUSIP)."""
    df = df.copy()
    df["is_odd_lot"] = (df["par_amount"] < ODD_LOT_PAR).astype(int)
    df["is_interdealer"] = (df["trade_type"] == "INTER_DEALER").astype(int)
    df["is_impossible_yield"] = ((df["yield"] <= impossible_lo) | (df["yield"] > impossible_hi)
                                 | df["yield"].isna()).astype(int)
    df["is_outlier"] = 0
    for _, g in df.groupby("cusip"):
        if len(g) < 5 or g["price"].isna().all():
            continue
        med = g["price"].median()
        mad = (g["price"] - med).abs().median()
        scale = 1.4826 * mad if mad > 0 else 0.25  # floor: 25 cents when prices are identical
        df.loc[g.index, "is_outlier"] = (((g["price"] - med).abs() / scale) > mad_k).astype(int)
    return df


def load_securities(path: Path = MANUAL / "securities.csv") -> pd.DataFrame:
    cols = ["cusip", "issuer_key", "description", "coupon", "maturity_date", "tax_exempt", "il_exempt",
            "is_callable", "call_date", "source_doc_url"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["cusip"] = df["cusip"].str.strip().str.upper()
    df["coupon"] = pd.to_numeric(df["coupon"], errors="coerce")
    # coupons may be given in percent (5.0) or decimal (0.05); anything >1 is percent
    df["coupon"] = df["coupon"].where(df["coupon"] <= 1, df["coupon"] / 100)
    df["maturity_date"] = pd.to_datetime(df["maturity_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for c in ("tax_exempt", "il_exempt", "is_callable"):
        df[c] = df[c].str.lower().isin(["1", "true", "yes", "y"]).astype(int)
    return df[cols]


def load_trades_files(folder: Path = MANUAL) -> pd.DataFrame:
    frames = []
    for p in sorted([*folder.glob("trades*.csv"), *folder.glob("new_issue*.csv")]):
        frames.append(normalize_trades(pd.read_csv(p, dtype=str)))
    if not frames:
        return pd.DataFrame(columns=["cusip", "trade_date", "trade_time", "price", "yield", "par_amount", "trade_type"])
    return pd.concat(frames, ignore_index=True)


def load_optional(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path)
    return df[[c for c in cols if c in df.columns]]
