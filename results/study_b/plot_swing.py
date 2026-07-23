# swing_equity.csv -> 수익곡선 HTML 차트
import os
import pandas as pd
import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE, "swing_equity.csv"), parse_dates=["date"])

SERIES = [
    ("eq_long",     "롱온리 Q5 (Sharpe 0.61)",       "#2ecc71", 2.6),
    ("eq_bench",    "벤치 동일가중 (0.49)",           "#888888", 1.8),
    ("eq_Btilt",    "B 롱틸트 0.7L/0.3숏 (0.49)",     "#3498db", 1.8),
    ("eq_A",        "A 롱숏 Q5-Q1 (0.01)",           "#e67e22", 1.8),
    ("eq_shortAll", "숏온리 -Q1 (-0.48)",            "#e74c3c", 1.8),
]
fig = go.Figure()
for col, name, color, w in SERIES:
    fig.add_trace(go.Scatter(x=df["date"], y=df[col], name=name,
                             mode="lines", line=dict(color=color, width=w)))
fig.add_hline(y=1.0, line=dict(color="rgba(255,255,255,0.25)", dash="dot"))
fig.update_layout(
    title="연구 B 스윙 백테스트 · mom_1m(20d) · 10일 홀딩 · PIT SPX 2021-08~2026-06 (gross, 비용 전)",
    yaxis_title="누적 (시작=1.0)", height=560, template="plotly_dark",
    legend=dict(orientation="h", y=1.08, x=1, xanchor="right", font=dict(size=11)),
    margin=dict(l=60, r=20, t=70, b=40))
out = os.path.join(os.path.dirname(os.path.dirname(HERE)), "results", "chart_swing_backtest.html")
fig.write_html(out, include_plotlyjs="cdn")
print("saved:", out)
