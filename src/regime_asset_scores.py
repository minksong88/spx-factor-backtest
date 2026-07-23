# ============================================================
# regime_asset_scores.py — 국면별 ETF 롱숏 스코어 맵 갱신기
#
#   무엇: 실질금리(TIPS) × 기대인플레(BEI) 4사분면 국면을 전체표본에서
#         오라클 세그먼트(Whittaker + 극값 스냅)로 잘라, 각 ETF의 국면별
#         반응 β( = %수익 / |Δ실질| )·평균수익·블록수를 계산해
#         날짜 스탬프 CSV + Markdown 스냅샷으로 저장한다.
#
#   국면축:  실질 = GTII10 Govt(bbg.market_data), BEI = USGGBE10 Index(bbg.market_data)
#            사분면 = (실질방향, BEI방향):
#              RF 리플레이션    (실질↑ BEI↑)
#              ST 스태그·완화기대(실질↓ BEI↑)
#              RC 침체·디스인플레(실질↓ BEI↓)
#              TG 긴축·디스인플레(실질↑ BEI↓)
#   스코어:  β = mean_over_blocks( 블록수익 / |Δ실질| ),  avg% = mean(블록수익%),  n = 블록수
#            (오라클 = 전체표본·완벽 국면타이밍. 실시간 매매성과와는 다름 — 방향표로만 사용.)
#
#   실행:    SUPABASE_DB_URL 환경변수(또는 리포 루트 .env) 설정 후
#              python src/regime_asset_scores.py
#            산출(날짜 안 쌓고 같은 파일 덮어씀):
#              results/regime_scores/regime_RF.csv  (리플레이션)
#              results/regime_scores/regime_ST.csv  (스태그·완화기대)
#              results/regime_scores/regime_RC.csv  (침체·디스인플레)
#              results/regime_scores/regime_TG.csv  (긴축·디스인플레)
#              results/regime_scores/README.md      (요약 + 읽는 법 + 마지막 갱신일)
#            각 CSV = 그 국면만, β 내림차순. 컬럼: rank,ticker,beta,avg_ret_pct,n_blocks,quadrant,regime
#
#   파라미터(hyo 계보와 동일): LAM=5000, MIN_DAYS_LEG=10, MIN_DREAL=0.15
# ============================================================
import os
import sys
import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 국면 파라미터 ----
TIPS_TICKER = "GTII10 Govt"      # 실질금리 10Y
BEI_TICKER = "USGGBE10 Index"    # 기대인플레(breakeven) 10Y
LAM = 5000                        # Whittaker-Henderson 평활 강도
MIN_DAYS_LEG = 10                 # 최소 레그 길이(일)
MIN_DREAL = 0.15                  # |Δ실질| 최소 필터(%p) — 미미한 움직임 블록 제외
QUAD = {(True, True): "RF", (False, True): "ST", (False, False): "RC", (True, False): "TG"}
QNAME = {
    "RF": "리플레이션(실질↑BEI↑)", "ST": "스태그·완화기대(실질↓BEI↑)",
    "RC": "침체·디스인플레(실질↓BEI↓)", "TG": "긴축·디스인플레(실질↑BEI↓)",
}
QDESC = {
    "RF": "성장·인플레 동반 상승. 경기민감·에너지·금융 강세, 금·귀금속 약세.",
    "ST": "실질↓+기대인플레↑. 실물·귀금속·성장 광범위 강세, 방어·필수소비 약세.",
    "RC": "성장·인플레 동반 둔화(안전자산 선호). 금·리츠·유틸 강세, 에너지·원자재 약세.",
    "TG": "실질↑+기대인플레↓(가장 힘든 국면). 헬스케어·방산·귀금속 상대강세, 고밸류·크립토·에너지 약세.",
}

# ---- ETF 유니버스 (64종) ----
UNIVERSE = [
    "ARTY", "BETZ", "BITO", "BLOK", "CIBR", "COPX", "DIA", "DRIV", "FCG", "FDN",
    "FINX", "FIW", "FNGS", "GDX", "GLD", "GRID", "IGV", "IHE", "IHI", "IJH",
    "IJR", "ITA", "ITB", "IWM", "IYT", "IYZ", "JETS", "KBE", "KIE", "KRE",
    "NLR", "OIH", "PBJ", "PBW", "PEJ", "QQQ", "QTUM", "REZ", "RNRG", "ROBO",
    "SIL", "SKYY", "SLV", "SOXX", "SPY", "SRVR", "TAN", "UNG", "USO", "XBI",
    "XHB", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU",
    "XLV", "XLY", "XME", "XRT",
]


# ---------------- DB ----------------
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


def _macro(engine, ticker, field="PX_LAST"):
    q = text("SELECT date, value FROM bbg.market_data WHERE ticker=:t AND field=:f ORDER BY date")
    df = pd.read_sql(q, engine, params={"t": ticker, "f": field})
    s = pd.to_numeric(df.set_index("date")["value"], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    return s


def _prices(engine, tickers, field="PX_LAST"):
    q = text("SELECT date, ticker, value FROM fmp.market_data "
             "WHERE ticker = ANY(:t) AND field=:f ORDER BY date")
    df = pd.read_sql(q, engine, params={"t": list(tickers), "f": field})
    p = df.pivot(index="date", columns="ticker", values="value").sort_index()
    p.index = pd.to_datetime(p.index)
    return p.astype(float)


# ---------------- 오라클 세그먼트 (Whittaker + 극값 스냅, 전체표본) ----------------
def whittaker_segs(y, lam=LAM, min_days=MIN_DAYS_LEG):
    """평활 후 기울기 부호로 up/down 세그먼트 분할, 짧은 레그는 이웃에 흡수."""
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    y = np.asarray(y, float)
    n = len(y)
    D = sparse.diags([1., -2., 1.], [0, 1, 2], shape=(n - 2, n))
    I = sparse.identity(n)
    tr = spsolve((I + lam * (D.T @ D)).tocsc(), y)
    sl = np.gradient(tr)
    arr = np.where(sl > 1e-9, "up", np.where(sl < -1e-9, "down", "flat"))

    def segs_of(a):
        s = []
        c = a[0]
        st = 0
        for i in range(1, len(a)):
            if a[i] != c:
                s.append([st, i - 1, c])
                c = a[i]
                st = i
        s.append([st, len(a) - 1, c])
        return s

    ch = True
    while ch:
        ch = False
        s = segs_of(arr)
        for j, (a, b, k) in enumerate(s):
            if b - a + 1 < min_days and len(s) > 1:
                ll = s[j - 1][1] - s[j - 1][0] + 1 if j > 0 else -1
                rl = s[j + 1][1] - s[j + 1][0] + 1 if j < len(s) - 1 else -1
                arr[a:b + 1] = s[j - 1][2] if ll >= rl else s[j + 1][2]
                ch = True
                break
    return segs_of(arr)


def snap_to_extrema(segs, mv):
    """up 세그먼트 끝을 구간 최고점, down 세그먼트 끝을 최저점으로 스냅."""
    mv = np.asarray(mv, float)
    S = [list(s) for s in segs]
    for k in range(len(S)):
        a, b, kind = S[k]
        if kind == "up":
            S[k].append(a + int(np.argmax(mv[a:b + 1])))
        elif kind == "down":
            S[k].append(a + int(np.argmin(mv[a:b + 1])))
        else:
            S[k].append(None)
    out = []
    for i in range(len(S)):
        a, b, kind, ext = S[i]
        if kind in ("up", "down") and ext is not None:
            out.append((a, ext, kind))
            if i + 1 < len(S):
                S[i + 1][0] = ext + 1
                if S[i + 1][0] > S[i + 1][1]:
                    S[i + 1][1] = S[i + 1][0]
        else:
            out.append((a, b, kind))
    out = [(a, b, k) for a, b, k in out if a <= b]
    merged = [list(out[0])]
    for a, b, k in out[1:]:
        if k == merged[-1][2] and a == merged[-1][1] + 1:
            merged[-1][1] = b
        else:
            merged.append([a, b, k])
    return [tuple(x) for x in merged]


def direction_of_window(series):
    """window 구간의 오라클 세그먼트 마지막 방향(up/down/flat)."""
    segs = snap_to_extrema(whittaker_segs(series.values), series.values)
    return segs[-1][2]


def build_regime_blocks(real, bei):
    """실질을 오라클 세그먼트로 자르고, 각 실질 레그의 BEI 방향으로 사분면 태깅.
       |Δ실질|>=MIN_DREAL 인 블록만 유지.
       반환: list of dict(quad, start, end, dreal)."""
    idx = real.index
    segs = snap_to_extrema(whittaker_segs(real.values), real.values)  # 실질 레그
    blocks = []
    for a, b, kind in segs:
        if kind not in ("up", "down"):
            continue
        s_dt, e_dt = idx[a], idx[b]
        dreal = float(real.iloc[b] - real.iloc[a])
        if abs(dreal) < MIN_DREAL:
            continue
        # 같은 창의 BEI 방향
        bei_win = bei.loc[s_dt:e_dt]
        if len(bei_win) < MIN_DAYS_LEG:
            continue
        bdir = direction_of_window(bei_win)
        if bdir not in ("up", "down"):
            bdir = "up" if bei_win.iloc[-1] >= bei_win.iloc[0] else "down"
        quad = QUAD[(kind == "up", bdir == "up")]
        blocks.append({"quad": quad, "start": s_dt, "end": e_dt, "dreal": dreal})
    return blocks


# ---------------- 스코어 ----------------
def compute_scores(blocks, px):
    """블록×ETF -> (quad, ticker)별 β / avg% / n."""
    recs = []
    for blk in blocks:
        q, s_dt, e_dt, dr = blk["quad"], blk["start"], blk["end"], blk["dreal"]
        denom = abs(dr) if abs(dr) >= 0.05 else 0.05
        win = px.loc[s_dt:e_dt]
        if len(win) < 2:
            continue
        first, last = win.iloc[0], win.iloc[-1]
        for tk in px.columns:
            p0, p1 = first.get(tk), last.get(tk)
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            bret = p1 / p0 - 1.0
            recs.append((q, tk, bret / denom, bret * 100.0))
    r = pd.DataFrame(recs, columns=["quadrant", "ticker", "beta_i", "ret_pct"])
    g = r.groupby(["quadrant", "ticker"]).agg(
        beta=("beta_i", "mean"), avg_ret_pct=("ret_pct", "mean"), n_blocks=("ret_pct", "size")
    ).reset_index()
    g["beta"] = g["beta"].round(2)
    g["avg_ret_pct"] = g["avg_ret_pct"].round(1)
    g["regime"] = g["quadrant"].map(QNAME)
    for q in QUAD.values():
        m = g["quadrant"] == q
        g.loc[m, "rank"] = g.loc[m, "beta"].rank(ascending=False, method="first")
    g["rank"] = g["rank"].astype(int)
    return g[["quadrant", "regime", "ticker", "beta", "avg_ret_pct", "n_blocks", "rank"]] \
        .sort_values(["quadrant", "rank"]).reset_index(drop=True)


# ---------------- 출력 (날짜 안 쌓고 같은 파일 덮어씀) ----------------
CSV_COLS = ["rank", "ticker", "beta", "avg_ret_pct", "n_blocks", "quadrant", "regime"]


def write_regime_csvs(g, outdir):
    """국면별로 분리해 regime_<Q>.csv 4개를 β 내림차순으로 덮어씀."""
    for q in ["RF", "ST", "RC", "TG"]:
        sub = g[g["quadrant"] == q].sort_values("beta", ascending=False).reset_index(drop=True)
        sub = sub.copy()
        sub["rank"] = range(1, len(sub) + 1)
        sub[CSV_COLS].to_csv(os.path.join(outdir, f"regime_{q}.csv"),
                             index=False, encoding="utf-8-sig")


def write_readme(g, blocks, date_str, path):
    order = ["RF", "ST", "RC", "TG"]
    nblk = {q: sum(1 for b in blocks if b["quad"] == q) for q in order}
    L = []
    L.append("# 국면별 ETF 롱숏 스코어 맵\n")
    L.append(f"> **마지막 갱신: {date_str}** (갱신 시 이 파일과 아래 CSV들을 **덮어씀** — 날짜 파일 안 쌓음)")
    L.append("> 계산 코드: **`src/regime_asset_scores.py`** — `python src/regime_asset_scores.py` 로 재생성.\n")
    L.append("## 파일 구성 (국면별로 분리)")
    L.append("| 국면 | 파일 | 뜻 |")
    L.append("|---|---|---|")
    for q in order:
        L.append(f"| **{q}** | `regime_{q}.csv` | {QNAME[q]} |")
    L.append("")
    L.append("각 CSV 컬럼: `rank, ticker, beta, avg_ret_pct, n_blocks, quadrant, regime`. "
             "**β 내림차순 정렬**(rank 1 = 그 국면 최강 롱). 뷰어에서 자유 정렬.\n")
    L.append("## 읽는 법 (중요)")
    L.append("- **β 부호 = 방향**((+)롱 후보 / (−)숏 후보). β = 실질금리 1%p당 자산 % 반응 = mean(블록수익 / |Δ실질|), 오라클(전체표본).")
    L.append("- **β 크기 비교는 같은 국면(=같은 파일) 안에서만** — 국면끼리 β 절대값 비교 금지(국면마다 Δ실질 스케일 다름).")
    L.append("- **avg% = 그 국면 평균 매수후보유 수익률**(체감용). **n_blocks 작으면(≤7) 신뢰도 낮음.**")
    L.append("- 직전 상대수익(리버설/모멘텀) 필터는 붙이지 말 것 — 실시간에선 위험조정수익을 못 올림. 국면을 사람이 정하고 쓰는 방향표.\n")
    L.append("## 국면별 요약 (롱 top3 / 숏 bottom3)")
    L.append("| 국면 | 대표 롱 (β 상위) | 대표 숏 (β 하위) |")
    L.append("|---|---|---|")
    for q in order:
        sub = g[g["quadrant"] == q].sort_values("beta", ascending=False)
        longs = " · ".join(sub.head(3)["ticker"].tolist())
        shorts = " · ".join(sub.tail(3).iloc[::-1]["ticker"].tolist())
        L.append(f"| **{q}** {QNAME[q]} · n≈{nblk[q]} | {longs} | {shorts} |")
    L.append("")
    L.append("## 갱신 방법")
    L.append("- 직접: `SUPABASE_DB_URL` 설정 후 `python src/regime_asset_scores.py` → README와 `regime_*.csv` 4개를 **같은 이름으로 덮어씀**.")
    L.append("- 또는 \"국면 스코어맵 갱신해줘\"라고 시키면 재계산해 같은 파일들 덮어쓰고 커밋(날짜 안 쌓음).\n")
    L.append("## 한계")
    L.append("- 전부 오라클(전체표본·완벽 국면타이밍) β → 실시간 매매성과와 다름. 방향표로만 사용. gross(무비용).")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    date_str = datetime.date.today().isoformat()
    outdir = os.path.join(ROOT, "results", "regime_scores")
    os.makedirs(outdir, exist_ok=True)

    engine = create_engine(_db_url(), connect_args={"connect_timeout": 30})
    print("[1/4] 매크로 로딩 (실질·BEI)…")
    real = _macro(engine, TIPS_TICKER)
    bei = _macro(engine, BEI_TICKER)
    common = real.index.intersection(bei.index)
    real, bei = real.reindex(common).dropna(), bei.reindex(common).dropna()
    common = real.index.intersection(bei.index)
    real, bei = real.reindex(common), bei.reindex(common)
    print(f"      실질 {real.index.min().date()}~{real.index.max().date()} ({len(real)}일)")

    print("[2/4] 오라클 국면 세그먼트…")
    blocks = build_regime_blocks(real, bei)
    from collections import Counter
    print("      블록:", dict(Counter(b["quad"] for b in blocks)), "| 총", len(blocks))

    print("[3/4] ETF 가격 로딩 + 스코어…")
    px = _prices(engine, UNIVERSE)
    g = compute_scores(blocks, px)

    print("[4/4] 저장 (국면별 CSV 4개 + README, 덮어쓰기)…")
    write_regime_csvs(g, outdir)
    write_readme(g, blocks, date_str, os.path.join(outdir, "README.md"))
    for q in ["RF", "ST", "RC", "TG"]:
        print("  ->", os.path.join("results/regime_scores", f"regime_{q}.csv"))
    print("  -> results/regime_scores/README.md  (마지막 갱신:", date_str + ")")


if __name__ == "__main__":
    main()
