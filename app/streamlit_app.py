"""Streamlit dashboard. Everything is read from the pipeline's SQLite database."""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from muni_monitor import analytics as an  # noqa: E402
from muni_monitor.db import DB_PATH  # noqa: E402

st.set_page_config(page_title="Illinois Muni Stress Monitor", layout="wide")
if not Path(DB_PATH).exists():
    st.error("Database not found. Run `python -m muni_monitor.pipeline` first.")
    st.stop()
con = sqlite3.connect(DB_PATH)
rd = lambda sql: pd.read_sql(sql, con)  # noqa: E731

st.title("Illinois Municipal Credit & Pension Stress Monitor")
st.caption("Public data, educational use. Not the MMD curve; spreads reflect liquidity as well as credit.")
tm = rd("SELECT * FROM trade_metrics")
names = dict(rd("SELECT issuer_key, name FROM issuers").values)
if tm.empty:
    st.warning("No municipal trades loaded. Download EMMA CSVs into data/manual/ (see DATA_SOURCES.md) "
               "and rerun the pipeline. Treasury and data-quality panels are live.")

t1, t2, t3, t4, t5 = st.tabs(["Issuers", "Single bond", "Pension", "Treasury", "Data quality"])
with t1:
    sc = rd("SELECT * FROM stress_scores")
    if sc.empty:
        st.info("Awaiting trade data.")
    else:
        sc["issuer"] = sc.issuer_key.map(names)
        st.dataframe(sc.drop(columns="issuer_key"), use_container_width=True, hide_index=True)
        ser = rd("SELECT * FROM issuer_spread_series")
        fig = px.line(ser, x="date", y="median_spread_bps", color="issuer_key", markers=True)
        for e in rd("SELECT * FROM events").itertuples():
            fig.add_vline(x=e.event_date, line_dash="dot", annotation_text=e.label)
        st.plotly_chart(fig, use_container_width=True)
        ratio = tm.groupby(["issuer_key", "bucket"])["muni_treasury_ratio"].median().reset_index()
        st.plotly_chart(px.bar(ratio, x="bucket", y="muni_treasury_ratio", color="issuer_key", barmode="group",
                               title="Median muni/Treasury yield ratio"), use_container_width=True)
with t2:
    sec = rd("SELECT * FROM securities")
    if sec.empty or tm.empty:
        st.info("Awaiting securities and trades.")
    else:
        cusip = st.selectbox("CUSIP", sec.cusip)
        b = tm[tm.cusip == cusip].sort_values("trade_date")
        if b.empty:
            st.info("No usable trades for this CUSIP.")
        else:
            last = b.iloc[-1]
            c = st.columns(4)
            c[0].metric("Yield", f"{last.yield_pct:.2f}%")
            c[1].metric("Spread", f"{last.spread_bps:.0f} bp")
            c[2].metric("Mod. duration", f"{last.modified_duration:.2f}")
            c[3].metric("Convexity", f"{last.convexity:.1f}")
            st.plotly_chart(px.line(b, x="trade_date", y="yield_pct", markers=True), use_container_width=True)
            tr = rd(f"SELECT trade_date, price FROM trades WHERE cusip='{cusip}' ORDER BY trade_date")
            st.plotly_chart(px.line(tr, x="trade_date", y="price", markers=True), use_container_width=True)
            st.subheader("Tax-equivalent yield")
            fed = st.selectbox("Federal bracket", an.FED_BRACKETS, index=4, format_func=lambda x: f"{x:.0%}")
            row = sec.set_index("cusip").loc[cusip]
            if bool(row.tax_exempt):
                # Illinois tax applies only if the bond is exempt from Illinois income tax
                # (il_exempt=1). Illinois GO and CPS official statements say they are NOT.
                st_rate = an.IL_INCOME_TAX if bool(row.il_exempt) else 0.0
                y = last.yield_pct / 100
                st.write(f"TEY: **{an.tax_equivalent_yield(y, fed, st_rate) * 100:.2f}%** "
                         f"({'federal + Illinois' if st_rate else 'federal only; interest is taxable by Illinois'})")
            else:
                st.write("This bond is flagged taxable; tax-equivalent yield does not apply.")
with t3:
    pen = rd("SELECT * FROM pension_metrics")
    if pen.empty:
        st.info("No pension data loaded (data/manual/pension_metrics.csv).")
    else:
        pen["series"] = pen.issuer_key + " " + pen.plan
        st.plotly_chart(px.line(pen, x="fiscal_year", y="funded_ratio_pct", color="series", markers=True),
                        use_container_width=True)
        ser = rd("SELECT * FROM issuer_spread_series")
        if not ser.empty:
            ser["year"] = pd.to_datetime(ser.date).dt.year
            st.plotly_chart(px.line(ser.groupby(["issuer_key", "year"]).median_spread_bps.mean().reset_index(),
                                    x="year", y="median_spread_bps", color="issuer_key", markers=True,
                                    title="Annual mean of median spread (bp)"), use_container_width=True)
with t4:
    cv = rd("SELECT * FROM treasury_curve")
    last_d = cv.date.max()
    cur = cv[cv.date == last_d].sort_values("tenor_years")
    st.plotly_chart(go.Figure(go.Scatter(x=cur.tenor_years, y=cur.par_yield_pct, mode="lines+markers"))
                    .update_layout(title=f"Par curve {last_d}", xaxis_type="log"), use_container_width=True)
with t5:
    dq = rd("SELECT * FROM dq_results WHERE run_ts=(SELECT MAX(run_ts) FROM dq_results)")
    st.dataframe(dq, use_container_width=True, hide_index=True)
