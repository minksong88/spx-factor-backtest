# ============================================================
# study_b_pick.py — 연구 B: 매크로 배제, 추정치·펀더멘탈·모멘텀 롱숏 종목선택
#
#   가설: 숏 = 과매수(RSI↑) + 고멀티플 + 펀더악화(퀄리티↓·추정치하향).
#         롱 = 반대. 단 모멘텀 최상위는 숏에서 제외(추세 크래시 가드).
#
#   구성: PIT SPX 유니버스 · 월말 리밸런스 · 크로스섹셔널 z-score 합성 ·
#         분위(quintile) 롱숏 · 포워드 1M 수익 · IC/성과지표/팩터분해.
#
#   실행: SUPABASE_DB_URL 필요.  python src/study_b_pick.py
# ============================================================
import os
import numpy as np
import pandas as pd

import data
import factors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "results", "study_b")

# ---------------- 설정 ----------------
START_REBAL = "2021-07-31"      # 추정치·유니버스 공통 시작
NQ = 5                          # 분위 수 (5=quintile)
MOM_GUARD_PCT = 0.90            # 모멘텀 상위 10%는 숏북에서 제외
REPORT_LAG = 60                 # 펀더멘탈 리포트 지연(일)
W = dict(value=1.0, quality=1.0, revision=1.0, rsi=1.0)   # 스코어 가중

VALUE_LOW = ["per", "pbr", "ev_to_ebitda"]      # 낮을수록 쌈(롱)
VALUE_HI = ["fcf_yield"]                          # 높을수록 쌈(롱)
QUAL_HI = ["roic", "net_margin", "operating_margin"]  # 높을수록 좋음(롱)
QUAL_LOW = ["debt_to_equity"]                    # 낮을수록 좋음(롱)
FUND_ALL = VALUE_LOW + VALUE_HI + QUAL_HI + QUAL_LOW


# ---------------- 데이터 로딩 ----------------
def load():
    mem = data.spx_membership()
    all_tk = sorted(mem["ticker"].unique())
    px = data.fetch_prices(all_tk, "PX_LAST").reindex(columns=all_tk)
    best_eps = data.fetch_estimates(all_tk, "BEST_EPS").reindex(columns=all_tk)
    fwd_pe = data.fetch_estimates(all_tk, "BEST_PE_RATIO").reindex(columns=all_tk)
    cal = px.index
    fund = {m: data.fundamentals_asof(all_tk, m, cal, REPORT_LAG).reindex(columns=all_tk)
            for m in FUND_ALL}
    return mem, all_tk, px, best_eps, fwd_pe, fund


def pit_masks(mem, all_tk, rebal):
    """리밸런스 시점별 PIT 유니버스 마스크 DataFrame(rebal x ticker, bool)."""
    snaps = sorted(mem["date"].unique())
    active = {d: set(mem[(mem["date"] == d) & (mem["is_active"])]["ticker"]) for d in snaps}
    mask = pd.DataFrame(False, index=rebal, columns=all_tk)
    for rd in rebal:
        valid = [d for d in snaps if d <= rd]
        if not valid:
            continue
        cur = active[max(valid)]
        mask.loc[rd, [t for t in all_tk if t in cur]] = True
    return mask


# ---------------- 팩터 조립 ----------------
def build_scores(px, best_eps, fwd_pe, fund, rebal, mask):
    rsi = factors.rsi(px)
    mom = factors.momentum(px)
    rev = factors.eps_revision(best_eps)

    def samp(df):
        return df.reindex(rebal).where(mask)      # 리밸런스일 샘플 + PIT 마스크

    Z = lambda df: factors.zscore_row(samp(df))

    # 밸류 (쌀수록 +): 낮은 멀티플 = +, 높은 fcf_yield = +, fwd_pe 낮을수록 +
    val_parts = [-Z(fund[m]) for m in VALUE_LOW] + [Z(fund[m]) for m in VALUE_HI] + [-Z(fwd_pe)]
    z_value = sum(val_parts) / len(val_parts)
    # 퀄리티 (좋을수록 +)
    qual_parts = [Z(fund[m]) for m in QUAL_HI] + [-Z(fund[m]) for m in QUAL_LOW]
    z_quality = sum(qual_parts) / len(qual_parts)
    # 추정치 리비전 (상향 +)
    z_rev = Z(rev)
    # 역과매수 (과매도 +) — RSI 높으면 숏 → 스코어에서 뺀다
    z_rsi = Z(rsi)

    score = (W["value"] * z_value + W["quality"] * z_quality
             + W["revision"] * z_rev - W["rsi"] * z_rsi)
    mom_s = samp(mom)
    parts = dict(value=z_value, quality=z_quality, revision=z_rev, anti_rsi=-z_rsi)
    return score, mom_s, parts


# ---------------- 백테스트 ----------------
def forward_returns(px, rebal):
    ps = px.reindex(rebal)
    return ps.shift(-1) / ps - 1.0            # rd_i -> rd_{i+1} 수익


def run_ls(score, fwd, mom_s, nq=NQ, guard=MOM_GUARD_PCT):
    """분위 롱숏 + 모멘텀 가드. -> DataFrame(index=rebal, [long,short,ls,ic,n])."""
    rows = []
    for rd in score.index[:-1]:                # 마지막은 포워드수익 없음
        s = score.loc[rd].dropna()
        fr = fwd.loc[rd]
        common = s.index.intersection(fr.dropna().index)
        s = s.loc[common]
        if len(s) < nq * 5:
            continue
        q = pd.qcut(s.rank(method="first"), nq, labels=False)
        long_t = s.index[q == nq - 1]
        short_t = s.index[q == 0]
        # 모멘텀 가드: 숏에서 모멘텀 상위 guard 분위 제외
        mrank = mom_s.loc[rd, common].rank(pct=True)
        short_t = [t for t in short_t if not (mrank.get(t, 0) >= guard)]
        lr = fr.loc[long_t].mean()
        sr = fr.loc[short_t].mean() if short_t else np.nan
        ic = s.corr(fr.loc[common], method="spearman")
        rows.append(dict(date=rd, long=lr, short=sr, ls=lr - sr, ic=ic,
                         n=len(common), n_short=len(short_t)))
    return pd.DataFrame(rows).set_index("date")


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print("로딩...")
    mem, all_tk, px, best_eps, fwd_pe, fund = load()
    # 밀집 거래일만(>=400종 가격 존재) — 주말/오염 날짜가 월말로 잡히는 것 방지
    dense = px.index[px.notna().sum(axis=1) >= 400]
    me = pd.Series(dense).groupby([dense.year, dense.month]).max()
    rebal = sorted(d for d in me if d >= pd.Timestamp(START_REBAL))
    print(f"유니버스 union {len(all_tk)}종 · 리밸런스 {len(rebal)}개월 "
          f"({rebal[0].date()}~{rebal[-1].date()})")
    mask = pit_masks(mem, all_tk, rebal)
    score, mom_s, parts = build_scores(px, best_eps, fwd_pe, fund, rebal, mask)
    fwd = forward_returns(px, rebal)

    res = run_ls(score, fwd, mom_s)
    print("\n===== 합성 스코어 롱숏 =====")
    print(res[["long", "short", "ls", "ic", "n", "n_short"]].round(4).to_string())
    print("\n[성과] LS:", factors.perf_stats(res["ls"]))
    print("[성과] Long:", factors.perf_stats(res["long"]))
    print(f"[IC] 평균 {res['ic'].mean():.3f}  ·  IR(IC) {res['ic'].mean()/res['ic'].std():.2f}")

    # 팩터 단독 분해
    print("\n===== 팩터 단독 IC/LS =====")
    dec = []
    for name, z in parts.items():
        r = run_ls(z, fwd, mom_s)
        st = factors.perf_stats(r["ls"])
        dec.append(dict(factor=name, mean_ic=round(r["ic"].mean(), 3),
                        ls_CAGR=st.get("CAGR"), ls_Sharpe=st.get("Sharpe")))
    dec = pd.DataFrame(dec)
    print(dec.to_string(index=False))

    res.to_csv(os.path.join(OUTDIR, "ls_composite.csv"), encoding="utf-8-sig")
    dec.to_csv(os.path.join(OUTDIR, "factor_decomp.csv"), index=False, encoding="utf-8-sig")
    print(f"\n[저장] {OUTDIR}")


if __name__ == "__main__":
    main()
