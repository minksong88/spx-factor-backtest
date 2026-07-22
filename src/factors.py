# ============================================================
# factors.py — 팩터 구성 유틸 (크로스섹셔널)
#
#   가격패널(wide: date x ticker)에서 RSI·모멘텀 계산,
#   임의 지표패널을 크로스섹셔널 z-score(윈저라이즈)로 표준화.
#   모든 함수는 look-ahead 없이 '해당 시점까지의' 데이터만 사용.
# ============================================================
import numpy as np
import pandas as pd


# ---------------- 기술적 지표 (가격패널 기반) ----------------
def rsi(prices, n=14):
    """Wilder RSI. prices: wide DataFrame(date x ticker) -> 동형 RSI(0~100)."""
    delta = prices.diff()
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    # Wilder 평활 (EMA, alpha=1/n)
    roll_up = up.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    roll_dn = dn.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = roll_up / roll_dn.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def momentum(prices, lookback=252, skip=21):
    """12-1M 모멘텀: P[t-skip]/P[t-lookback]-1 (최근 skip일 제외)."""
    return prices.shift(skip) / prices.shift(lookback) - 1.0


def eps_revision(best_eps, window=63):
    """추정치 리비전: BEST_EPS[t]/BEST_EPS[t-window]-1 (window≈영업일 3M)."""
    prev = best_eps.shift(window)
    return best_eps / prev.where(prev > 0) - 1.0


# ---------------- 크로스섹셔널 표준화 ----------------
def zscore_row(df, winsor=3.0):
    """각 날짜(row) 내에서 크로스섹셔널 z-score. winsor 표준편차로 클리핑."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0.0, np.nan)
    z = df.sub(mu, axis=0).div(sd, axis=0)
    if winsor:
        z = z.clip(lower=-winsor, upper=winsor)
    return z


def rank_pct_row(df):
    """각 날짜 내 백분위 순위(0~1). 이상치에 강건 — z 대안."""
    return df.rank(axis=1, pct=True)


# ---------------- 성과지표 ----------------
def perf_stats(ret, periods_per_year=12):
    """월간 수익률 시계열 -> dict(CAGR, vol, Sharpe, MDD, hit)."""
    ret = ret.dropna()
    if len(ret) == 0:
        return {}
    eq = (1.0 + ret).cumprod()
    yrs = len(ret) / periods_per_year
    cagr = eq.iloc[-1] ** (1.0 / yrs) - 1.0 if yrs > 0 else np.nan
    vol = ret.std() * np.sqrt(periods_per_year)
    sharpe = (ret.mean() * periods_per_year) / vol if vol else np.nan
    mdd = (eq / eq.cummax() - 1.0).min()
    return dict(CAGR=round(cagr, 4), vol=round(vol, 4), Sharpe=round(sharpe, 2),
                MDD=round(mdd, 4), hit=round((ret > 0).mean(), 3), n=len(ret))
