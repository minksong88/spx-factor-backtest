# 매크로 롱숏: 2W하위 제외 필터 유무 백테스트 비교 (국면단위)
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE, "gate_backtest_regime_returns.csv"), parse_dates=["enddate"])

def stats(pct):
    r = pct/100.0
    eq = (1+r).cumprod()
    return dict(total_ret=round(eq.iloc[-1]-1,3), mean_per_regime=round(r.mean(),4),
                std=round(r.std(),4), sharpe_per_regime=round(r.mean()/r.std(),2),
                hit=round((r>0).mean(),2), MDD=round((eq/eq.cummax()-1).min(),3), n=len(r))

rows = {"매크로LS 전체(필터X)":"ls_base_pct", "매크로LS + 2W하위제외(필터O)":"ls_filt_pct"}
tbl = pd.DataFrame({k: stats(df[v]) for k,v in rows.items()}).T
print(tbl.to_string())

fig = go.Figure()
COL = {"ls_base_pct":("#e67e22","매크로LS 전체 (필터X)"), "ls_filt_pct":("#2ecc71","매크로LS + 2W하위 제외 (필터O)")}
for v,(c,name) in COL.items():
    eq = (1+df[v]/100).cumprod()
    eq = pd.concat([pd.Series([1.0]), eq], ignore_index=True)
    x = [df["enddate"].iloc[0]] + list(df["enddate"])
    fig.add_trace(go.Scatter(x=x, y=eq, name=name, mode="lines+markers", line=dict(color=c, width=2.4)))
fig.add_hline(y=1.0, line=dict(color="rgba(255,255,255,0.2)", dash="dot"))
fig.update_layout(
    title="매크로 롱숏(반응맵 top/bottom 3분위) — 2W 하위 제외 필터 유무 · ETF64 · 국면단위 (gross)",
    yaxis_title="누적 (시작=1.0)", yaxis_type="log", height=540, template="plotly_dark",
    legend=dict(orientation="h", y=1.08, x=1, xanchor="right"), margin=dict(l=60,r=20,t=70,b=40))
out = os.path.join(os.path.dirname(HERE), "chart_gate_backtest.html")
fig.write_html(out, include_plotlyjs="cdn")
print("saved:", out)
tbl.to_csv(os.path.join(HERE, "gate_backtest_stats.csv"), encoding="utf-8-sig")
