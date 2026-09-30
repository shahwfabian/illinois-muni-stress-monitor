"""Generate and execute notebooks/validation.ipynb (each analytics function vs known values)."""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
cells = [
    ("md", "# Analytics validation\nEach function is checked against a closed-form or textbook value. "
           "Asserts fail the notebook if a check breaks."),
    ("code", "import sys; sys.path.insert(0, '../src')\nfrom datetime import date\nimport numpy as np\n"
             "from muni_monitor import analytics as an\nS, M = date(2020,1,15), date(2030,1,15)"),
    ("md", "## Price: 10y 6% semiannual at 6% yield = par\n"),
    ("code", "p = an.price_from_yield(S, M, 0.06, 0.06)['clean']; print(p); assert abs(p-100) < 1e-9"),
    ("md", "## Price: 10y 8% at 6% yield = 4*a(20,3%) + 100*1.03^-20 = 114.877"),
    ("code", "p = an.price_from_yield(S, M, 0.08, 0.06)['clean']; print(round(p,4)); assert abs(p-114.877) < 1e-3"),
    ("md", "## Yield from price (round trip, off-coupon date)"),
    ("code", "st = date(2021,3,10)\npx = an.price_from_yield(st, M, 0.05, 0.0375)['clean']\n"
             "y = an.yield_from_price(st, M, 0.05, px); print(y); assert abs(y-0.0375) < 1e-9"),
    ("md", "## Duration: par bond modified duration = (1 - 1.03^-20)/0.06 = 7.4387"),
    ("code", "r = an.risk_measures(S, M, 0.06, 0.06); print(r); assert abs(r['modified']-(1-1.03**-20)/0.06) < 1e-9"),
    ("md", "## DV01 and convexity vs finite differences"),
    ("code", "y,h = 0.045,1e-5; f = lambda v: an.price_from_yield(S,M,0.05,v)['dirty']\n"
             "r = an.risk_measures(S,M,0.05,y)\n"
             "assert abs(r['dv01']-(f(y-1e-4)-f(y+1e-4))/2) < 1e-4*r['dv01']\n"
             "assert abs(r['convexity']-(f(y+h)-2*f(y)+f(y-h))/(h*h*f(y))) < 1e-3*r['convexity']; print('ok', r)"),
    ("md", "## Zero coupon: Macaulay duration equals maturity"),
    ("code", "assert abs(an.risk_measures(S, M, 0.0, 0.05)['macaulay']-10) < 1e-9; print('ok')"),
    ("md", "## Curve interpolation: hits knots, monotone between them"),
    ("code", "x=np.array([1,2,5,10,30.]); y=np.array([4.0,4.2,4.5,4.8,5.2])\n"
             "assert abs(an.interpolate_curve(x,y,5)-4.5)<1e-12\n"
             "v=[an.interpolate_curve(x,y,t) for t in np.linspace(1,30,100)]; assert all(b>=a-1e-12 for a,b in zip(v,v[1:])); print('ok')"),
    ("md", "## Spread, ratio, tax-equivalent yield"),
    ("code", "assert abs(an.spread_bps(0.0425,0.04)-25)<1e-9\nassert abs(an.muni_treasury_ratio(0.034,0.04)-0.85)<1e-12\n"
             "print(an.tax_equivalent_yield(0.04,0.37), an.tax_equivalent_yield(0.04,0.24,an.IL_INCOME_TAX))"),
]
nb = nbf.v4.new_notebook()
nb.cells = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in cells]
out = ROOT / "notebooks"
out.mkdir(exist_ok=True)
NotebookClient(nb, timeout=120, resources={"metadata": {"path": str(out)}}).execute()
nbf.write(nb, out / "validation.ipynb")
print("executed notebooks/validation.ipynb")
