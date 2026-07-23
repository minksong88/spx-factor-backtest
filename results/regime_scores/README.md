# 국면별 ETF 롱숏 스코어 맵

> **마지막 갱신: 2026-07-23** (데이터 2026-07-22까지 · 갱신 시 이 파일과 아래 CSV들을 **덮어씀** — 날짜 파일 안 쌓음)
> 계산 코드: **`src/regime_asset_scores.py`** — `python src/regime_asset_scores.py` 로 재생성.

## 파일 구성 (국면별로 분리)
| 국면 | 파일 | 뜻 | 블록수 |
|---|---|---|---|
| **RF** | `regime_RF.csv` | 리플레이션(실질↑BEI↑) | 13 |
| **ST** | `regime_ST.csv` | 스태그·완화기대(실질↓BEI↑) | 10 |
| **RC** | `regime_RC.csv` | 침체·디스인플레(실질↓BEI↓) | 10 |
| **TG** | `regime_TG.csv` | 긴축·디스인플레(실질↑BEI↓) | 11 |

각 CSV 컬럼: `rank, ticker, beta, avg_ret_pct, n_blocks, quadrant, regime`. **β 내림차순**(rank 1 = 그 국면 최강 롱, 64 = 최강 숏). 뷰어에서 자유 정렬.

## 읽는 법 (중요)
- **β 부호 = 방향**((+)롱 후보 / (−)숏 후보). β = 실질금리 1%p당 자산 % 반응 = mean(블록수익 / |Δ실질|).
- **β 크기 비교는 같은 국면(=같은 파일) 안에서만** — 국면끼리 β 절대값 비교 금지(국면마다 Δ실질 스케일 다름).
- **avg% = 그 국면 평균 매수후보유 수익률**(체감용). **n_blocks 작으면(≤7) 신뢰도 낮음.**
- 직전 상대수익(리버설/모멘텀) 필터는 붙이지 말 것 — 실시간에선 위험조정수익을 못 올림. 국면을 사람이 정하고 쓰는 방향표.

## 국면별 요약 (롱 top3 / 숏 bottom3)
| 국면 | 대표 롱 | 대표 숏 |
|---|---|---|
| **RF** 리플레이션(실질↑BEI↑) · n≈13 | USO · KRE · KBE | GDX · SIL · UNG |
| **ST** 스태그·완화기대(실질↓BEI↑) · n≈10 | BLOK · GDX · FNGS | JETS · XLE · PEJ |
| **RC** 침체·디스인플레(실질↓BEI↓) · n≈10 | GDX · SIL · BLOK | UNG · OIH · FCG |
| **TG** 긴축·디스인플레(실질↑BEI↓) · n≈11 | SOXX · XBI · IHE | BITO · BLOK · SRVR |

## 국면 관통 패턴 (참고)
- 금·귀금속(GDX/SIL/SLV/GLD): RF 최악 → ST·RC 최고. 실질금리 역행.
- 에너지·원자재(USO/FCG/OIH/COPX/XLE): RF 최고 → RC·TG 최악. 리플레이션 베타.
- 은행(KRE/KBE): RF 강세(금리 스팁), 그 외 중립~약세.
- 크립토·고멀티플(BITO/BLOK/BETZ): TG 최약(고 duration).

## 갱신 방법
- 직접: `SUPABASE_DB_URL` 설정 후 `python src/regime_asset_scores.py` → README와 `regime_*.csv` 4개 **덮어씀**.
- 또는 "국면 스코어맵 갱신해줘" → 최신 DB로 재계산해 같은 파일들 덮어쓰고 커밋(날짜 안 쌓음).

## 한계
- 국면 구간은 전체표본으로 확정(하인드사이트) → 실시간 매매성과와 다름. 방향표로만 사용. gross(무비용).
