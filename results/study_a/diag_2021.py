import os, pandas as pd, numpy as np, plotly.graph_objects as go
HERE=os.path.dirname(os.path.abspath(__file__))
orc=pd.read_csv(os.path.join(HERE,"tipsbei_daily_returns.csv"),parse_dates=["date"])[["date","r_base"]].rename(columns={"r_base":"oracle"})
ong=pd.read_csv(os.path.join(HERE,"filter_extc_returns.csv"),parse_dates=["date"])[["date","r_base"]].rename(columns={"r_base":"ongoing"})
df=pd.merge(orc,ong,on="date",how="outer").sort_values("date").fillna(0.0).reset_index(drop=True)
def st(r,dates,lo=None):
    m=pd.Series(True,index=r.index) if lo is None else (dates>=pd.Timestamp(lo)).values
    rr=r[m]; d=dates[m]; eq=(1+rr).cumprod(); yrs=(d.iloc[-1]-d.iloc[0]).days/365.25
    return dict(total=round((eq.iloc[-1]-1)*100,0),CAGR=round((eq.iloc[-1]**(1/yrs)-1)*100,1),
        sharpe=round(rr.mean()/rr.std()*np.sqrt(252),2),MDD=round((eq/eq.cummax()-1).min()*100,1))
rows=[]
for nm,c in [("오라클(정답국면)","oracle"),("극점스냅 ongoing","ongoing")]:
    rows.append(dict(전략=nm,구간="전체(18~)",**st(df[c],df.date)))
    rows.append(dict(전략=nm,구간="2021~",**st(df[c],df.date,"2021-01-01")))
tbl=pd.DataFrame(rows); print(tbl.to_string(index=False))
# chart: 2021 rebased
sub=df[df.date>=pd.Timestamp("2021-01-01")].copy()
fig=go.Figure()
for c,col,nm in [("oracle","#2ecc71","오라클(정답국면) 2021~"),("ongoing","#e67e22","극점스냅 ongoing 2021~")]:
    eq=(1+sub[c]).cumprod()
    fig.add_trace(go.Scatter(x=sub.date,y=eq,name=nm,mode="lines",line=dict(color=col,width=2.4)))
fig.add_hline(y=1.0,line=dict(color="rgba(255,255,255,0.25)",dash="dot"))
fig.update_layout(title="매크로 롱숏(tercile) 2021~ 리베이스 — 오라클 vs 극점스냅 ongoing (일별, gross)",
    yaxis_title="누적(2021=1)", height=520, template="plotly_dark",
    legend=dict(orientation="h",y=1.08,x=1,xanchor="right"), margin=dict(l=60,r=20,t=60,b=40))
out=os.path.join(os.path.dirname(HERE),"chart_diag_2021.html"); fig.write_html(out,include_plotlyjs="cdn")
print("saved:",out)
