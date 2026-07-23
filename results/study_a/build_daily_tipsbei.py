import json, os
import pandas as pd, numpy as np, plotly.graph_objects as go
SRC = "/root/.claude/projects/-home-user-macro-reaction-backtest/c950405a-5afc-5c3f-91ea-7afa2909e2de/tool-results/mcp-Supabase-execute_sql-1784773796469.txt"
res = json.loads(open(SRC).read())["result"]
arr = res[res.index("["): res.rindex("]")+1]
df = pd.DataFrame(json.loads(arr))
df["date"] = pd.to_datetime(df["date"])
for c in ["r_base","r_logic"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
df = df.sort_values("date").reset_index(drop=True)
HERE = os.path.dirname(os.path.abspath(__file__))
df.to_csv(os.path.join(HERE,"tipsbei_daily_returns.csv"), index=False)

def stats(r, dates):
    eq=(1+r).cumprod(); yrs=(dates.iloc[-1]-dates.iloc[0]).days/365.25
    return dict(total_pct=round((eq.iloc[-1]-1)*100,0), CAGR_pct=round((eq.iloc[-1]**(1/yrs)-1)*100,1),
        ann_vol_pct=round(r.std()*np.sqrt(252)*100,1), sharpe=round(r.mean()/r.std()*np.sqrt(252),2),
        MDD_pct=round((eq/eq.cummax()-1).min()*100,1), days=len(r))
tbl=pd.DataFrame({"오라클 매크로단독(base)":stats(df.r_base,df.date),
                  "매크로+2W리버설(logic)":stats(df.r_logic,df.date)}).T
print(tbl.to_string()); tbl.to_csv(os.path.join(HERE,"tipsbei_daily_stats.csv"),encoding="utf-8-sig")

fig=go.Figure()
for c,col,name,w in [("r_base","#e67e22","오라클 매크로단독 (base)",2.2),
                     ("r_logic","#2ecc71","매크로 + 2W 리버설 (우호·눌린 롱 / 불리·과열 숏)",2.6)]:
    eq=(1+df[c]).cumprod()
    fig.add_trace(go.Scatter(x=df.date,y=eq,name=name,mode="lines",line=dict(color=col,width=w)))
fig.add_hline(y=1.0,line=dict(color="rgba(255,255,255,0.2)",dash="dot"))
fig.update_layout(title="TIPS/BEI 오라클 롱숏 — 매크로단독 vs 매크로+2W리버설 · 일별 누적 · ETF64 (gross, 시장중립)",
    yaxis_title="누적(시작=1.0)", yaxis_type="log", height=560, template="plotly_dark",
    legend=dict(orientation="h",y=1.08,x=1,xanchor="right",font=dict(size=10)), margin=dict(l=60,r=20,t=70,b=40))
out=os.path.join(os.path.dirname(HERE),"chart_tipsbei_daily.html"); fig.write_html(out,include_plotlyjs="cdn")
print("saved:",out,"| rows:",len(df),str(df.date.min().date()),"~",str(df.date.max().date()))
