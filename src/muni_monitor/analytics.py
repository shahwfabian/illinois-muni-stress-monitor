"""Fixed income analytics implemented from first principles.

Conventions (stated explicitly):
  * Municipal bonds: 30/360 (US/NASD) day count, semiannual coupons, street-convention
    price/yield (fractional first period discounted at compound semiannual yield).
  * Treasuries: ACT/ACT for accrued and the fractional period, semiannual coupons.
  * Prices are per 100 par. Yields are decimals (0.05 = 5%).
"""
from __future__ import annotations

from datetime import date

import numpy as np
from dateutil.relativedelta import relativedelta
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

FED_BRACKETS = (0.22, 0.24, 0.32, 0.35, 0.37)
FED_TOP_WITH_NIIT = 0.408  # 37% + 3.8% NIIT (NIIT applies to the taxable alternative)
IL_INCOME_TAX = 0.0495  # Illinois flat individual income tax rate (IL Dept. of Revenue)


def days_30_360(d1: date, d2: date) -> int:
    """US (NASD) 30/360 day count. End-of-February rules are not applied."""
    dd1, dd2 = d1.day, d2.day
    if dd1 == 31:
        dd1 = 30
    if dd2 == 31 and dd1 == 30:
        dd2 = 30
    return 360 * (d2.year - d1.year) + 30 * (d2.month - d1.month) + (dd2 - dd1)


def _days(d1: date, d2: date, dc: str) -> int:
    if dc == "30/360":
        return days_30_360(d1, d2)
    if dc == "ACT/ACT":
        return (d2 - d1).days
    raise ValueError(f"unknown day count {dc!r}")


def coupon_schedule(settle: date, maturity: date, freq: int = 2) -> tuple[date, list[date]]:
    """Return (previous coupon date, remaining coupon dates > settle), anchored on maturity."""
    if maturity <= settle:
        raise ValueError("maturity must be after settlement")
    step = 12 // freq
    dates: list[date] = []
    k = 0
    d = maturity
    while d > settle:
        dates.append(d)
        k += 1
        d = maturity - relativedelta(months=step * k)
    dates.reverse()
    return d, dates


def cashflows(settle: date, maturity: date, coupon: float, freq: int = 2,
              dc: str = "30/360") -> tuple[np.ndarray, np.ndarray, float]:
    """Periods-from-settlement (w+i), cash flows per 100, and the accrual fraction w."""
    prev, dates = coupon_schedule(settle, maturity, freq)
    nxt = dates[0]
    w = _days(settle, nxt, dc) / _days(prev, nxt, dc)
    n = len(dates)
    periods = w + np.arange(n)
    cfs = np.full(n, 100.0 * coupon / freq)
    cfs[-1] += 100.0
    return periods, cfs, w


def price_from_yield(settle: date, maturity: date, coupon: float, ytm: float,
                     freq: int = 2, dc: str = "30/360") -> dict[str, float]:
    """Dirty, clean price and accrued interest per 100 par."""
    periods, cfs, w = cashflows(settle, maturity, coupon, freq, dc)
    dirty = float(np.sum(cfs / (1 + ytm / freq) ** periods))
    accrued = 100.0 * coupon / freq * (1 - w)
    return {"dirty": dirty, "clean": dirty - accrued, "accrued": accrued}


def yield_from_price(settle: date, maturity: date, coupon: float, clean_price: float,
                     freq: int = 2, dc: str = "30/360") -> float:
    """Solve the yield for a clean price with Brent's method."""
    def f(y: float) -> float:
        return price_from_yield(settle, maturity, coupon, y, freq, dc)["clean"] - clean_price
    return float(brentq(f, -0.05, 1.0, xtol=1e-12))


def risk_measures(settle: date, maturity: date, coupon: float, ytm: float,
                  freq: int = 2, dc: str = "30/360") -> dict[str, float]:
    """Macaulay/modified duration (years), convexity (years^2), DV01 (per 100 par)."""
    periods, cfs, _ = cashflows(settle, maturity, coupon, freq, dc)
    pv = cfs / (1 + ytm / freq) ** periods
    dirty = pv.sum()
    mac = float(np.sum(periods / freq * pv) / dirty)
    mod = mac / (1 + ytm / freq)
    conv = float(np.sum(pv * periods * (periods + 1)) / (freq**2 * (1 + ytm / freq) ** 2) / dirty)
    return {"macaulay": mac, "modified": mod, "convexity": conv, "dv01": mod * dirty * 1e-4}


def interpolate_curve(tenors: np.ndarray, yields: np.ndarray, t: float) -> float:
    """Monotone cubic (PCHIP) interpolation of a par curve at maturity t (years).

    PCHIP never overshoots between knots (a natural cubic spline can create spurious humps
    on flat or inverted curves). No extrapolation: NaN outside the tenor range.
    """
    x, y = np.asarray(tenors, float), np.asarray(yields, float)
    m = ~np.isnan(y)
    x, y = x[m], y[m]
    if len(x) < 2 or t < x.min() or t > x.max():
        return float("nan")
    return float(PchipInterpolator(x, y)(t))


def spread_bps(muni_yield: float, treasury_yield: float) -> float:
    """Yield spread to Treasury in basis points (decimals in)."""
    return (muni_yield - treasury_yield) * 1e4


def muni_treasury_ratio(muni_yield: float, treasury_yield: float) -> float:
    """Muni-to-Treasury yield ratio (0.85 = 85%)."""
    return muni_yield / treasury_yield


def combined_rate(fed: float, state: float = 0.0) -> float:
    """Combined marginal rate. Assumes no federal deduction of state tax (SALT cap)."""
    return fed + state


def tax_equivalent_yield(y: float, fed: float, state: float = 0.0) -> float:
    """Taxable-equivalent yield of a tax-exempt yield y at the given marginal rates."""
    r = combined_rate(fed, state)
    if not 0 <= r < 1:
        raise ValueError("combined rate must be in [0, 1)")
    return y / (1 - r)
