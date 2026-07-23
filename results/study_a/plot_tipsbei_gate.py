# TIPS/BEI 오라클 매크로 롱숏 — 2W 필터 방향 비교 (하위제외 vs 상위제외 vs 무)
import os, pandas as pd, numpy as np, plotly.graph_objects as go
HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE,"tipsbei_gate_regime_returns.csv"), parse_dates=["enddate"])

def stats(pct):
    r=pct/100.0; eq=(1+r).cumprod()
    return dict(total_pct=round((eq.iloc[-1]-1)*100,0), mean_regime=round(r.mean()*100,2),
                std=round(r.std()*100,2), sharpe_reg=round(r.mean()/r.std(),2),
                hit=round((r>0).mean(),2), MDD=round((eq/eq.cummax()-1).min()*100,1), n=len(r))
tbl=pd.DataFrame({"오라클 base(필터無)":stats(df.ls_base),
                  "2W하위제외(10Y식)":stats(df.ls_excl_2wLow),
                  "2W상위제외(TIPS/BEI식)":stats(df.ls_excl_2wHigh)}).T
print(tbl.to_string()); tbl.to_csv(os.path.join(HERE,"tipsbei_gate_stats.csv"),encoding="utf-8-sig")

fig=go.Figure()
for col,c,name,w in [("ls_base","#e67e22","오라클 base (필터無)",2.6),
                     ("ls_excl_2wLow","#e74c3c","2W 하위제외 (10Y식·역효과?)",1.8),
                     ("ls_excl_2wHigh","#2ecc71","2W 상위제외 (TIPS/BEI식)",2.6)]:
    eq=(1+df[col]/100).cumprod(); x=[df.enddate.iloc[0]]+list(df.enddate); y=[1.0]+list(eq)
    fig.add_trace(go.Scatter(x=x,y=y,name=name,mode="lines",line=dict(color=c,width=w)))
fig.add_hline(y=1.0,line=dict(color="rgba(255,255,255,0.2)",dash="dot"))
fig.update_layout(title="TIPS/BEI 사분면 오라클 매크로 롱숏 — 2W 포지셔닝 필터 방향 비교 · ETF64 · 국면단위 (gross)",
    yaxis_title="누적(시작=1.0)", yaxis_type="log", height=560, template="plotly_dark",
    legend=dict(orientation="h",y=1.1,x=1,xanchor="right",font=dict(size=10)), margin=dict(l=60,r=20,t=70,b=40))
out=os.path.join(os.path.dirname(HERE),"chart_tipsbei_gate.html"); fig.write_html(out,include_plotlyjs="cdn")
print("saved:",out)
