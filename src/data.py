# ============================================================
# data.py — Supabase 데이터 접근 계층 (SPX 팩터 백테스트 공통)
#
#   소스 요약 (2026-07 확인):
#     · bbg.index_members  : SPX/NDX 시점별 구성종목(월간 스냅샷, is_active). 생존편향 없음.
#     · bbg.market_data    : BEST_EPS / BEST_SALES / BEST_PE_RATIO (일별 포워드 컨센서스),
#                            USGG10YR 등 매크로. field 컬럼으로 구분.
#     · fmp.market_data    : 개별종목 일봉 OHLCV (PX_LAST/OPEN/HIGH/LOW/VOLUME).
#     · fmp.fundamentals   : 트레일링 펀더멘탈 13종(분기, long: fiscal_date/period/metric/value).
#     · fmp.market_cap     : 시가총액(일별).
#
#   접속: SUPABASE_DB_URL 환경변수 또는 리포 루트 .env (SUPABASE_DB_URL=postgresql://...)
# ============================================================
import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 트레일링 펀더멘탈 지표 목록 (fmp.fundamentals.metric) ----
FUND_METRICS = [
    "per", "pbr", "ev_to_ebitda", "fcf_yield", "dividend_yield",       # 밸류/멀티플
    "gross_margin", "operating_margin", "net_margin", "roic",           # 수익성/퀄리티
    "debt_to_equity", "net_debt_to_ebitda", "interest_coverage",        # 레버리지/리스크
    "capex_to_ocf", "fcf_per_share",                                    # 현금흐름
]
# ---- 포워드 추정치 필드 (bbg.market_data.field) ----
EST_FIELDS = ["BEST_EPS", "BEST_SALES", "BEST_PE_RATIO"]


def _db_url():
    u = os.environ.get("SUPABASE_DB_URL")
    if not u:
        p = os.path.join(ROOT, ".env")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8-sig"):
                if line.strip().startswith("SUPABASE_DB_URL="):
                    u = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not u:
        sys.exit("SUPABASE_DB_URL 환경변수(또는 리포 루트 .env)가 필요합니다.")
    if u.startswith("postgresql://"):
        u = u.replace("postgresql://", "postgresql+psycopg2://", 1)
    return u


_ENGINE = create_engine(_db_url(), connect_args={"connect_timeout": 30})


# ---------------- 유니버스 (시점별 SPX, 생존편향 제거) ----------------
def spx_membership(index_ticker="SPX Index"):
    """월간 스냅샷 원자료 -> DataFrame(date, ticker, is_active)."""
    q = text("SELECT date, ticker, is_active FROM bbg.index_members "
             "WHERE index_ticker=:ix ORDER BY date, ticker")
    df = pd.read_sql(q, _ENGINE, params={"ix": index_ticker})
    df["date"] = pd.to_datetime(df["date"])
    return df


def pit_universe(as_of, index_ticker="SPX Index"):
    """as_of 시점에 유효한 최신 스냅샷의 활성 구성종목 리스트."""
    mem = spx_membership(index_ticker)
    snaps = mem["date"].unique()
    valid = [d for d in snaps if d <= pd.Timestamp(as_of)]
    if not valid:
        return []
    snap = max(valid)
    sub = mem[(mem["date"] == snap) & (mem["is_active"])]
    return sorted(sub["ticker"].tolist())


# ---------------- 가격 (개별종목 일봉) ----------------
def fetch_prices(tickers, field="PX_LAST"):
    """fmp.market_data -> wide DataFrame(index=date, columns=ticker)."""
    q = text("SELECT date, ticker, value FROM fmp.market_data "
             "WHERE ticker = ANY(:t) AND field=:f ORDER BY date")
    df = pd.read_sql(q, _ENGINE, params={"t": list(tickers), "f": field})
    p = df.pivot(index="date", columns="ticker", values="value").sort_index()
    p.index = pd.to_datetime(p.index)
    return p.astype(float)


# ---------------- 포워드 추정치 (블룸버그 BEst, 일별) ----------------
def fetch_estimates(tickers, field="BEST_EPS"):
    """bbg.market_data -> wide DataFrame(index=date, columns=ticker). field in EST_FIELDS."""
    q = text("SELECT date, ticker, value FROM bbg.market_data "
             "WHERE ticker = ANY(:t) AND field=:f ORDER BY date")
    df = pd.read_sql(q, _ENGINE, params={"t": list(tickers), "f": field})
    p = df.pivot(index="date", columns="ticker", values="value").sort_index()
    p.index = pd.to_datetime(p.index)
    return p.astype(float)


# ---------------- 매크로 (10Y 등) ----------------
def fetch_macro(ticker="USGG10YR Index", field="PX_LAST"):
    q = text("SELECT date, value FROM bbg.market_data "
             "WHERE ticker=:t AND field=:f ORDER BY date")
    df = pd.read_sql(q, _ENGINE, params={"t": ticker, "f": field})
    s = df.set_index("date")["value"]
    s.index = pd.to_datetime(s.index)
    return pd.to_numeric(s, errors="coerce").dropna()


# ---------------- 트레일링 펀더멘탈 (분기 long) ----------------
def fetch_fundamentals(tickers, metrics=None):
    """fmp.fundamentals -> long DataFrame(fiscal_date, ticker, period, metric, value).
       fiscal_date = 분기말(리포트 실제 공개는 이후) → PIT 정렬 시 report_lag 적용 필요."""
    metrics = metrics or FUND_METRICS
    q = text("SELECT fiscal_date, ticker, period, metric, value FROM fmp.fundamentals "
             "WHERE ticker = ANY(:t) AND metric = ANY(:m) ORDER BY ticker, metric, fiscal_date")
    df = pd.read_sql(q, _ENGINE, params={"t": list(tickers), "m": list(metrics)})
    df["fiscal_date"] = pd.to_datetime(df["fiscal_date"])
    return df


def fundamentals_asof(tickers, metric, calendar, report_lag_days=60):
    """분기 펀더멘탈을 일별 캘린더에 PIT 정렬.
       각 값은 (fiscal_date + report_lag_days) 이후부터 사용 가능하도록 시프트 후 ffill.
       -> wide DataFrame(index=calendar, columns=ticker). look-ahead 방지."""
    df = fetch_fundamentals(tickers, [metric])
    df["avail"] = df["fiscal_date"] + pd.Timedelta(days=report_lag_days)
    w = df.pivot_table(index="avail", columns="ticker", values="value", aggfunc="last").sort_index()
    w.index = pd.to_datetime(w.index)
    cal = pd.DatetimeIndex(calendar)
    return w.reindex(w.index.union(cal)).ffill().reindex(cal)


if __name__ == "__main__":
    # 스모크 테스트 (SUPABASE_DB_URL 있을 때)
    uni = pit_universe("2024-01-31")
    print(f"SPX PIT 2024-01-31: {len(uni)}종  (예: {uni[:5]})")
    px = fetch_prices(uni[:5])
    print(f"가격 shape: {px.shape}  {px.index.min().date()}~{px.index.max().date()}")
    eps = fetch_estimates(uni[:5], "BEST_EPS")
    print(f"BEST_EPS shape: {eps.shape}")
