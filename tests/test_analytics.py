from datetime import date

import numpy as np
import pytest

from muni_monitor import analytics as an

S, M = date(2020, 1, 15), date(2030, 1, 15)  # on a coupon date, 10y


def test_par_bond_prices_at_par():
    p = an.price_from_yield(S, M, 0.06, 0.06)
    assert p["clean"] == pytest.approx(100.0, abs=1e-9)
    assert p["accrued"] == 0.0


def test_textbook_premium_bond():
    # 10y 8% semiannual at 6% yield: 100 + 4*(1-1.03^-20)/0.03 - 100*(1-1.03^-20)... closed form
    a = (1 - 1.03**-20) / 0.03
    expected = 4 * a + 100 * 1.03**-20
    assert an.price_from_yield(S, M, 0.08, 0.06)["clean"] == pytest.approx(expected, abs=1e-9)
    assert expected == pytest.approx(114.877, abs=1e-3)


def test_yield_price_roundtrip_off_coupon_date():
    st = date(2021, 3, 10)
    p = an.price_from_yield(st, M, 0.05, 0.0375)["clean"]
    assert an.yield_from_price(st, M, 0.05, p) == pytest.approx(0.0375, abs=1e-9)


def test_accrued_30_360():
    # 2 months (60/360-day) into a 180-day period at 6% coupon: 3 * 60/180 = 1.0
    st = date(2020, 3, 15)
    assert an.price_from_yield(st, M, 0.06, 0.06)["accrued"] == pytest.approx(1.0)


def test_par_bond_modified_duration_closed_form():
    r = an.risk_measures(S, M, 0.06, 0.06)
    assert r["modified"] == pytest.approx((1 - 1.03**-20) / 0.06, rel=1e-9)  # 7.4387
    assert r["macaulay"] == pytest.approx(r["modified"] * 1.03)


def test_dv01_and_convexity_match_finite_difference():
    y, h = 0.045, 1e-5
    p = lambda yy: an.price_from_yield(S, M, 0.05, yy)["dirty"]
    r = an.risk_measures(S, M, 0.05, y)
    assert r["dv01"] == pytest.approx((p(y - 1e-4) - p(y + 1e-4)) / 2, rel=1e-4)
    assert r["convexity"] == pytest.approx((p(y + h) - 2 * p(y) + p(y - h)) / (h**2 * p(y)), rel=1e-4)


def test_zero_coupon_macaulay_equals_maturity():
    r = an.risk_measures(S, M, 0.0, 0.05)
    assert r["macaulay"] == pytest.approx(10.0)


def test_day_counts():
    assert an.days_30_360(date(2020, 1, 31), date(2020, 3, 31)) == 60
    assert an.days_30_360(date(2020, 1, 15), date(2020, 7, 15)) == 180


def test_interpolation_hits_knots_and_is_monotone():
    x = np.array([1, 2, 5, 10, 30.0])
    y = np.array([4.0, 4.2, 4.5, 4.8, 5.2])
    assert an.interpolate_curve(x, y, 5.0) == pytest.approx(4.5)
    v = [an.interpolate_curve(x, y, t) for t in np.linspace(1, 30, 60)]
    assert all(b >= a - 1e-12 for a, b in zip(v, v[1:]))
    assert np.isnan(an.interpolate_curve(x, y, 0.5)) and np.isnan(an.interpolate_curve(x, y, 31))


def test_interpolation_ignores_nan_knots():
    x = np.array([1, 2, 5.0])
    y = np.array([4.0, np.nan, 4.6])
    assert an.interpolate_curve(x, y, 3.0) == pytest.approx(4.0 + 0.6 * 2 / 4, abs=0.2)


def test_spread_ratio_tey():
    assert an.spread_bps(0.0425, 0.0400) == pytest.approx(25.0)
    assert an.muni_treasury_ratio(0.034, 0.04) == pytest.approx(0.85)
    assert an.tax_equivalent_yield(0.04, 0.37) == pytest.approx(0.04 / 0.63)
    assert an.tax_equivalent_yield(0.04, 0.24, 0.0495) == pytest.approx(0.04 / (1 - 0.2895))
    with pytest.raises(ValueError):
        an.tax_equivalent_yield(0.04, 1.0)


def test_maturity_before_settle_raises():
    with pytest.raises(ValueError):
        an.price_from_yield(M, S, 0.05, 0.05)
