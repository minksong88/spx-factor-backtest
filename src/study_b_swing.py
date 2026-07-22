# ============================================================
# study_b_swing.py — 연구 B 실전 롱숏 백테스트 (스윙, 모멘텀 코어)
#
#   코어 신호: mom_1m(20일)  ※ SIGNAL='rsi20'/'disp20'로 교체 가능(근사 동일)
#   유니버스: PIT SPX (생존편향 없음), 리밸런스/홀딩 = REBAL_STEP 영업일(비중복)
#   분위(5): Q5=승자(롱), Q1=패자(숏).
#
#   전략:
#     A (대칭 달러중립):   long Q5, short Q1, 각 1x            r = mean(Q5) - mean(Q1)
#     B (롱틸트+숏 퀄리티필터): long Q5 (LONG_W),
#                            short = Q1 ∩ net_margin 하위절반 (SHORT_W)
#                            r = LONG_W*mean(long) - SHORT_W*mean(short_filt)
#   레그 분리(롱온리/숏온리), 벤치=동일가중 유니버스.
#   산출: 수익곡선·CAGR·연변동·Sharpe·MDD·승률·회전율 + CSV + plotly 차트.
#
#   실행: SUPABASE_DB_URL 필요.  python src/study_b_swing.py
#   ※ DB 적재 중이면 느릴 수 있음. 로직은 SQL 검증본과 동일.
# ============================================================
import os
import numpy as np
import pandas as pd

import data
import factors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "results", "study_b")

# ---------------- 설정 ----------------
START = "2021-08-01"
REBAL_STEP = 10          # 리밸런스/홀딩 영업일 (10=2주 스윙). 20이면 월간.
NQ = 5
SIGNAL = "mom_1m"        # 'mom_1m' | 'rsi20' | 'disp20'
MOM_LB = 20              # mom_1m 룩백
LONG_W, SHORT_W = 0.7, 0.3    # B 롱틸트 비중
REPORT_LAG = 60
PERIODS_PER_YEAR = 252 / REBAL_STEP


def build_signal(px):
    if SIGNAL == "mom_1m":
        return px / px.shift(MOM_LB) - 1.0
    if SIGNAL == "rsi20":
        return factors.rsi(px, 20)
    if SIGNAL == "disp20":
        return px / px.rolling(20).mean() - 1.0
    raise ValueError(SIGNAL)


def load():
    mem = data.spx_membership()
    all_tk = sorted(mem["ticker"].unique())
    px = data.fetch_prices(all_tk, "PX_LAST").reindex(columns=all_tk)
    # 밀집 거래일만 (오염 날짜 제거)
    px = px[px.notna().sum(axis=1) >= 400]
    nm = data.fundamentals_asof(all_tk, "net_margin", px.index, REPORT_LAG).reindex(columns=all_tk)
    return mem, all_tk, px, nm


def pit_active(mem):
    snaps = sorted(mem["date"].unique())
    active = {d: set(mem[(mem["date"] == d) & mem["is_active"]]["ticker"]) for d in snaps}
    def f(rd):
        v = [d for d in snaps if d <= rd]
        return active[max(v)] if v else set()
    return f


def backtest():
    os.makedirs(OUTDIR, exist_ok=True)
    mem, all_tk, px, nm = load()
    sig = build_signal(px)
    active_of = pit_active(mem)

    cal = px.index
    idx = [i for i in range(MOM_LB, len(cal) - REBAL_STEP, REBAL_STEP) if cal[i] >= pd.Timestamp(START)]

    rows, prev_long, prev_short = [], set(), set()
    for i in idx:
        rd, rnext = cal[i], cal[i + REBAL_STEP]
        uni = [t for t in all_tk if t in active_of(rd)]
        s = sig.loc[rd, uni].dropna()
        fwd = (px.loc[rnext, s.index] / px.loc[rd, s.index] - 1.0).dropna()
        common = s.index.intersection(fwd.index)
        if len(common) < NQ * 8:
            continue
        s, fwd = s.loc[common], fwd.loc[common]
        q = pd.qcut(s.rank(method="first"), NQ, labels=False)
        longs = set(s.index[q == NQ - 1])
        shorts = set(s.index[q == 0])
        # B: 숏 퀄리티 필터 — net_margin 하위절반(약펀더)만 숏
        nmv = nm.loc[rd, list(shorts)].dropna()
        med = nm.loc[rd, common].median()
        shorts_weak = set(nmv[nmv < med].index) if len(nmv) else set()

        lr = fwd[list(longs)].mean()
        sr = fwd[list(shorts)].mean()
        srw = fwd[list(shorts_weak)].mean() if shorts_weak else 0.0
        mkt = fwd.mean()
        # 회전율 (롱북 교체율)
        to = 1.0 - len(longs & prev_long) / len(longs) if prev_long else np.nan
        prev_long, prev_short = longs, shorts
        rows.append(dict(date=rd, longR=lr, shortR=sr, shortWeakR=srw, mkt=mkt,
                         retA=lr - sr, retB=LONG_W * lr - SHORT_W * srw,
                         n=len(common), nShortWeak=len(shorts_weak), turnover=to))
    return pd.DataFrame(rows).set_index("date")


def stats(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / PERIODS_PER_YEAR
    return dict(
        totRet=round(eq.iloc[-1] - 1, 3), CAGR=round(eq.iloc[-1] ** (1 / yrs) - 1, 4),
        vol=round(r.std() * np.sqrt(PERIODS_PER_YEAR), 4),
        Sharpe=round(r.mean() / r.std() * np.sqrt(PERIODS_PER_YEAR), 2) if r.std() else np.nan,
        MDD=round((eq / eq.cummax() - 1).min(), 4), hit=round((r > 0).mean(), 3), n=len(r))


def main():
    bt = backtest()
    print(f"기간 {bt.index[0].date()}~{bt.index[-1].date()} · {len(bt)}회 리밸런스 "
          f"(홀딩 {REBAL_STEP}영업일) · 신호 {SIGNAL}")
    cols = {"retA": "A(대칭 Q5-Q1)", "retB": f"B(롱틸트{LONG_W:.0%}/{SHORT_W:.0%}+숏퀄필터)",
            "longR": "롱온리(Q5)", "shortR": "숏온리(Q1,부호그대로)", "mkt": "벤치(동일가중)"}
    tbl = pd.DataFrame({nm_: stats(bt[c]) for c, nm_ in cols.items()}).T
    print("\n===== 성과 요약 =====")
    print(tbl.to_string())
    print(f"\n평균 회전율(롱북): {bt['turnover'].mean():.1%} / 리밸런스")
    print(f"평균 숏(약펀더) 종목수: {bt['nShortWeak'].mean():.0f}")

    bt.to_csv(os.path.join(OUTDIR, "swing_backtest_returns.csv"), encoding="utf-8-sig")
    tbl.to_csv(os.path.join(OUTDIR, "swing_backtest_stats.csv"), encoding="utf-8-sig")

    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        for c, nm_ in cols.items():
            eq = (1 + bt[c].dropna()).cumprod()
            fig.add_trace(go.Scatter(x=eq.index, y=eq, name=nm_, mode="lines"))
        fig.update_layout(title=f"연구 B 스윙 백테스트 · {SIGNAL} · 홀딩 {REBAL_STEP}일 (gross, 비용 전)",
                          yaxis_type="log", height=520, template="plotly_dark")
        fig.write_html(os.path.join(ROOT, "results", "chart_swing_backtest.html"), include_plotlyjs="cdn")
    except Exception as e:
        print("차트 스킵:", e)
    print(f"\n[저장] {OUTDIR}")
    print("※ gross 성과(거래비용·차입료 전). 스윙 회전율 높으니 net은 비용 반영 후 재평가 필수.")


if __name__ == "__main__":
    main()
