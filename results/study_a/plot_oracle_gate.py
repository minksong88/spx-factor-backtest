# 오라클(전체표본 정답맵) 매크로 롱숏 — 2W하위 제외 필터 유무 비교
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
orc = pd.read_csv(os.path.join(HERE, "oracle_gate_regime_returns.csv"), parse_dates=["enddate"])
exp = pd.read_csv(os.path.join(HERE, "gate_backtest_regime_returns.csv"), parse_dates=["enddate"])

def stats(pct):
    r = pct/100.0; eq = (1+r).cumprod()
    return dict(total_ret_pct=round((eq.iloc[-1]-1)*100,0), mean_regime_pct=round(r.mean()*100,2),
                std_pct=round(r.std()*100,2), sharpe_regime=round(r.mean()/r.std(),2),
                hit=round((r>0).mean(),2), MDD_pct=round((eq/eq.cummax()-1).min()*100,1), n=len(r))

tbl = pd.DataFrame({
    "오라클 전체(필터X)": stats(orc.ls_base_pct),
    "오라클 + 2W하위제외(필터O)": stats(orc.ls_filt_pct),
    "확장윈도우 전체(참고,정직)": stats(exp.ls_base_pct),
    "확장윈도우 + 필터(참고)": stats(exp.ls_filt_pct),
}).T
print(tbl.to_string())
tbl.to_csv(os.path.join(HERE, "oracle_gate_stats.csv"), encoding="utf-8-sig")

def eqline(df, col):
    eq = (1+df[col]/100).cumprod()
    return [df.enddate.iloc[0]]+list(df.enddate), [1.0]+list(eq)

fig = go.Figure()
series = [
 (orc,"ls_base_pct","#e67e22","오라클 전체 (필터X)",2.6),
 (orc,"ls_filt_pct","#2ecc71","오라클 + 2W하위 제외 (필터O)",2.8),
 (exp,"ls_base_pct","rgba(230,150,80,0.5)","확장윈도우 전체 (정직·참고)",1.6),
 (exp,"ls_filt_pct","rgba(90,200,120,0.5)","확장윈도우+필터 (참고)",1.6),
]
for df,col,c,name,w in series:
    x,y = eqline(df,col)
    fig.add_trace(go.Scatter(x=x,y=y,name=name,mode="lines",line=dict(color=c,width=w)))
fig.add_hline(y=1.0,line=dict(color="rgba(255,255,255,0.2)",dash="dot"))
fig.update_layout(title="오라클 매크로 롱숏 (정답맵) — 2W 하위 제외 필터 유무 · ETF64 · 국면단위 (gross)",
    yaxis_title="누적 (시작=1.0)", yaxis_type="log", height=560, template="plotly_dark",
    legend=dict(orientation="h",y=1.1,x=1,xanchor="right",font=dict(size=10)), margin=dict(l=60,r=20,t=70,b=40))
out = os.path.join(os.path.dirname(HERE),"chart_oracle_gate.html")
fig.write_html(out, include_plotlyjs="cdn")
print("saved:", out)
