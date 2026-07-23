# 5x5 매크로 x 2W이전수익 히트맵
import os
import plotly.graph_objects as go

# macro_q(1..5) x recent2w_q(1..5) -> within-regime excess return %
Z = [  # rows macro 1(불리)..5(우호), cols recent 1(빠짐)..5(오름)
 [-0.94,-0.75,-2.87,-0.99,-3.42],
 [-1.85, 0.60,-2.54,-0.58, 0.48],
 [-0.79, 0.00, 1.98,-0.78,-0.48],
 [-0.31, 0.61,-0.31, 1.01,-1.48],
 [ 0.22, 0.73, 3.56, 4.25, 5.24],
]
xr = ["1 빠짐","2","3","4","5 오름"]
yr = ["1 불리","2","3","4","5 우호"]
fig = go.Figure(go.Heatmap(
    z=Z, x=xr, y=yr, colorscale="RdBu", zmid=0, zmin=-5.5, zmax=5.5,
    text=[[f"{v:+.1f}" for v in row] for row in Z], texttemplate="%{text}",
    textfont=dict(size=13), colorbar=dict(title="국면내<br>초과수익%")))
fig.update_layout(
    title="매크로 반응맵(β) × 2W 이전수익 — 국면내 초과수익% (확장윈도우, ETF64, 38국면)",
    xaxis_title="2W 이전수익 분위 (이미 얼마나 올랐나)",
    yaxis_title="매크로 우호도 분위 (β, 국면 시작 전 점수)",
    height=520, template="plotly_dark", margin=dict(l=90,r=20,t=70,b=60))
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chart_macro_x_positioning.html")
fig.write_html(out, include_plotlyjs="cdn")
print("saved:", out)
