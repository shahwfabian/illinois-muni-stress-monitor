"""Build web/index.html (+ data.json) from the SQLite database for static hosting (Vercel).

Every number on the page comes from the database; nothing is hard-coded. Panels that need
municipal trades render an explicit empty state until trades are ingested.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from muni_monitor.db import DB_PATH  # noqa: E402


def q(con, sql):
    return pd.read_sql(sql, con).to_dict("records")


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    curve = pd.read_sql("SELECT * FROM treasury_curve", con)
    latest = curve.date.max()
    hist = curve[curve.tenor_label.isin(["2 Yr", "10 Yr", "30 Yr"])].pivot(
        index="date", columns="tenor_label", values="par_yield_pct").reset_index().sort_values("date")
    prior = sorted(curve.date.unique())[-22] if curve.date.nunique() > 22 else curve.date.min()
    dq_ts = con.execute("SELECT MAX(run_ts) FROM dq_results").fetchone()[0]
    data = {
        "asof": latest, "prior": prior,
        "curve_latest": curve[curve.date == latest].sort_values("tenor_years")[["tenor_label", "tenor_years", "par_yield_pct"]].to_dict("records"),
        "curve_prior": curve[curve.date == prior].sort_values("tenor_years")[["tenor_label", "tenor_years", "par_yield_pct"]].to_dict("records"),
        "history": hist.where(hist.notna(), None).to_dict("list"),
        "issuers": q(con, "SELECT * FROM issuers"),
        "n_securities": con.execute("SELECT COUNT(*) FROM securities").fetchone()[0],
        "n_trades": con.execute("SELECT COUNT(*) FROM trade_metrics").fetchone()[0],
        "stress": q(con, "SELECT * FROM stress_scores"),
        "series": q(con, "SELECT * FROM issuer_spread_series ORDER BY date"),
        "pension": q(con, "SELECT * FROM pension_metrics ORDER BY fiscal_year"),
        "events": q(con, "SELECT * FROM events"),
        "dq": q(con, f"SELECT check_name,severity,n_flagged,n_total,detail FROM dq_results WHERE run_ts='{dq_ts}'"),
        "dq_ts": dq_ts,
    }
    out = ROOT / "web"
    out.mkdir(exist_ok=True)
    (out / "data.json").write_text(json.dumps(data), encoding="utf-8")
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote web/index.html  asof={latest} trades={data['n_trades']} dq_checks={len(data['dq'])}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Illinois Muni Credit Stress Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root{--bg:#fafaf8;--fg:#1c1f24;--mut:#6b7280;--card:#fff;--bd:#e5e5e0;--a:#1f4e79;--warn:#b45309;--bad:#b91c1c;--ok:#15803d}
@media(prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e8e8e6;--mut:#9aa0a6;--card:#1c1f24;--bd:#2c3037;--a:#7fb2e5;--warn:#f0a44b;--bad:#f87171;--ok:#4ade80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 10px}.sub{color:var(--mut);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-bottom:16px}
.banner{border-left:4px solid var(--warn)}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--bd)}th{color:var(--mut);font-weight:600}
.pass{color:var(--ok)}.warn{color:var(--warn)}.fail{color:var(--bad)}.info{color:var(--mut)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.grid{grid-template-columns:1fr}}
.foot{color:var(--mut);font-size:13px}
</style></head><body><main>
<h1>Illinois Municipal Credit &amp; Pension Stress Monitor</h1>
<p class="sub">Market-implied credit health of State of Illinois GO, City of Chicago GO and Chicago Public Schools, measured as yield spread to the U.S. Treasury curve, alongside pension funding. Educational use; all inputs are public data.</p>
<div id="banner"></div>
<div class="card"><h2>Issuer comparison</h2><div id="stress"></div></div>
<div class="grid"><div class="card"><h2>Spread to Treasury (median trade spread, bp)</h2><div id="spread"></div></div>
<div class="card"><h2>Pension funded ratio (%)</h2><div id="pension"></div></div></div>
<div class="grid"><div class="card"><h2>U.S. Treasury par curve (benchmark)</h2><div id="curve"></div></div>
<div class="card"><h2>Treasury 2Y / 10Y / 30Y history</h2><div id="hist"></div></div></div>
<div class="card"><h2>Data quality (latest pipeline run)</h2><div id="dq"></div></div>
<p class="foot">Not the MMD curve. Trade data is sparse and noisy; spreads reflect liquidity as well as credit. See METHODOLOGY.md. Treasury data: home.treasury.gov, cross-checked to FRED.</p>
<script>
const D=__DATA__;
const L={margin:{t:10,r:10,b:40,l:50},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:getComputedStyle(document.body).color},legend:{orientation:'h'}};
const empty=(id,t)=>document.getElementById(id).innerHTML='<p class="sub">'+t+'</p>';
if(D.n_trades){document.getElementById('banner').innerHTML='<div class="card banner"><b>Primary-market data.</b> Spreads use new-issue reoffering yields from issuer Official Statements ('+D.n_trades+' bonds), not secondary trades. Tax-exempt, 7-12y bucket. EMMA trade CSVs can be added manually (see DATA_SOURCES.md).</div>'}else{document.getElementById('banner').innerHTML='<div class="card banner"><b>No municipal trades loaded yet.</b> EMMA prohibits automated access, so trade CSVs must be downloaded manually into <code>data/manual/</code> (see DATA_SOURCES.md), then run the pipeline. Treasury benchmark and data-quality panels below are live from the pipeline.</div>'}
const names=Object.fromEntries(D.issuers.map(i=>[i.issuer_key,i.name]));
if(D.stress.length){
 let h='<table><tr><th>Issuer</th><th>Spread (bp)</th><th>20-obs change (bp)</th><th>Funded ratio</th><th>Stress score</th><th>Notes</th></tr>';
 D.stress.forEach(s=>h+=`<tr><td>${names[s.issuer_key]}</td><td>${s.spread_bps.toFixed(0)}</td><td>${s.spread_change_bps==null?'n/a':s.spread_change_bps.toFixed(0)}</td><td>${s.funded_ratio_pct==null?'n/a':s.funded_ratio_pct.toFixed(1)+'%'}</td><td><b>${s.stress_score.toFixed(0)}</b></td><td>${s.notes||''}</td></tr>`);
 document.getElementById('stress').innerHTML=h+'</table>';
}else empty('stress','Awaiting trade data.');
if(D.series.length){
 const tr=Object.keys(names).filter(k=>D.series.some(r=>r.issuer_key==k)).map(k=>{const r=D.series.filter(x=>x.issuer_key==k);return{x:r.map(x=>x.date),y:r.map(x=>x.median_spread_bps),name:k,mode:'lines+markers'}});
 const sh=D.events.map(e=>({type:'line',x0:e.event_date,x1:e.event_date,yref:'paper',y0:0,y1:1,line:{dash:'dot',width:1,color:'#888'}}));
 const an=D.events.map(e=>({x:e.event_date,yref:'paper',y:1,text:e.label,showarrow:false,textangle:-90,font:{size:10}}));
 Plotly.newPlot('spread',tr,{...L,shapes:sh,annotations:an,yaxis:{title:'bp'}},{responsive:true});
}else empty('spread','Awaiting trade data.');
if(D.pension.length){
 const keys=[...new Set(D.pension.map(p=>p.issuer_key+' '+p.plan))];
 Plotly.newPlot('pension',keys.map(k=>{const r=D.pension.filter(p=>p.issuer_key+' '+p.plan==k);return{x:r.map(p=>p.fiscal_year),y:r.map(p=>p.funded_ratio_pct),name:k,mode:'lines+markers'}}),{...L,yaxis:{title:'%'}},{responsive:true});
}else empty('pension','No pension data loaded (data/manual/pension_metrics.csv).');
Plotly.newPlot('curve',[{x:D.curve_latest.map(r=>r.tenor_years),y:D.curve_latest.map(r=>r.par_yield_pct),name:D.asof,mode:'lines+markers'},{x:D.curve_prior.map(r=>r.tenor_years),y:D.curve_prior.map(r=>r.par_yield_pct),name:D.prior,mode:'lines',line:{dash:'dot'}}],{...L,xaxis:{title:'years',type:'log'},yaxis:{title:'par yield %'}},{responsive:true});
Plotly.newPlot('hist',['2 Yr','10 Yr','30 Yr'].map(k=>({x:D.history.date,y:D.history[k],name:k,mode:'lines'})),{...L,yaxis:{title:'%'}},{responsive:true});
let t='<table><tr><th>Check</th><th>Status</th><th>Flagged</th><th>Detail</th></tr>';
D.dq.forEach(d=>t+=`<tr><td>${d.check_name}</td><td class="${d.severity}">${d.severity}</td><td>${d.n_flagged}/${d.n_total}</td><td>${d.detail}</td></tr>`);
document.getElementById('dq').innerHTML=t+`</table><p class="foot">Run at ${D.dq_ts} UTC. Treasury data as of ${D.asof}.</p>`;
</script></main></body></html>"""

if __name__ == "__main__":
    main()
