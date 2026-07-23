import json, os
import pandas as pd, numpy as np, plotly.graph_objects as go
SRC="/root/.claude/projects/-home-user-macro-reaction-backtest/c950405a-5afc-5c3f-91ea-7afa2909e2de/tool-results/mcp-Supabase-execute_sql-1784784786915.txt"
res=json.loads(open(SRC).read())["result"]; arr=res[res.index("["):res.rindex("]")+1]
df=pd.DataFrame(json.loads(arr)); df["date"]=pd.to_datetime(df["date"])
cols=["r_base","r_mom","r_rev"]
for c in cols: df[c]=pd.to_numeric(df[c],errors="coerce").fillna(0.0)
df=df.sort_values("date").reset_index(drop=True)
HERE=os.path.dirname(os.path.abspath(__file__)); df.to_csv(os.path.join(HERE,"continuous_returns.csv"),index=False)
def stats(r,dates):
    eq=(1+r).cumprod(); yrs=(dates.iloc[-1]-dates.iloc[0]).days/365.25
    m21=dates>=pd.Timestamp("2021-01-01"); r21=r[m21]
    return dict(total_pct=round((eq.iloc[-1]-1)*100,0), CAGR=round((eq.iloc[-1]**(1/yrs)-1)*100,1),
        vol=round(r.std()*np.sqrt(252)*100,1), sharpe=round(r.mean()/r.std()*np.sqrt(252),2),
        MDD=round((eq/eq.cummax()-1).min()*100,1), sharpe21=round(r21.mean()/r21.std()*np.sqrt(252),2))
names={"r_base":"base(매크로z만·국면내고정)","r_mom":"매크로z+모멘텀z (연속리밸)","r_rev":"매크로z−모멘텀z=리버설 (연속리밸)"}
tbl=pd.DataFrame({names[c]:stats(df[c],df.date) for c in cols}).T
print(tbl.to_string()); tbl.to_csv(os.path.join(HERE,"continuous_stats.csv"),encoding="utf-8-sig")
fig=go.Figure(); sty={"r_base":("#e67e22",2.6),"r_mom":("#2ecc71",2.4),"r_rev":("#e74c3c",1.9)}
for c in cols:
    eq=(1+df[c]).cumprod(); col,w=sty[c]
    fig.add_trace(go.Scatter(x=df.date,y=eq,name=names[c],mode="lines",line=dict(color=col,width=w)))
fig.add_hline(y=1.0,line=dict(color="rgba(255,255,255,0.2)",dash="dot"))
fig.update_layout(title="점수합산(매크로z+모멘텀z) 연속리밸 상위6롱/하위6숏 · 극점스냅 causal 국면 · 일별 (gross)",
    yaxis_title="누적(시작=1.0)", yaxis_type="log", height=560, template="plotly_dark",
    legend=dict(orientation="h",y=1.09,x=1,xanchor="right",font=dict(size=9)), margin=dict(l=60,r=20,t=70,b=40))
out=os.path.join(os.path.dirname(HERE),"chart_continuous.html"); fig.write_html(out,include_plotlyjs="cdn")
print("saved:",out,"| days:",len(df))
