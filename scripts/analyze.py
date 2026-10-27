"""머니트렌드 2027 BTC 비중 vs SCHD:QLD 6:4 + 도파민 10% 연도별 계산.
세전·달러·수정종가(배당 재투자)·연 1회 1월 리밸런싱. BTC는 BTC-USD 현물가격(수수료·세금·환율 제외)."""
import json, hashlib
from pathlib import Path
import yfinance as yf
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKERS = ["SCHD", "QLD", "BTC-USD"]
START, END = "2014-12-01", "2026-10-28"

raw = yf.download(TICKERS, start=START, end=END, auto_adjust=True, progress=False)["Close"]
raw.to_csv(ROOT / "data" / "prices.csv")
ye = raw.resample("YE").last()          # 연말 종가 (BTC 주말 포함 마지막 거래 가격)
ye = ye[ye.index.year >= 2014]
ret = ye.pct_change().dropna()
ret.index = ret.index.year
last = raw.dropna().index[-1]
# 2026은 연초~마지막 공통 거래일
ytd = raw.loc[:last].ffill().iloc[-1] / ye.loc[ye.index.year == 2025].iloc[0] - 1
ret.loc[2026] = ytd

MIXES = {
    "A_SCHD60_QLD40": {"SCHD": .60, "QLD": .40, "BTC-USD": 0},
    "B_9010_dopamineBTC": {"SCHD": .54, "QLD": .36, "BTC-USD": .10},
    "C_book_cons_BTC5": {"SCHD": .57, "QLD": .38, "BTC-USD": .05},
    "D_dopamine_zero": {"SCHD": .54, "QLD": .36, "BTC-USD": 0},  # 10%는 현금(이자 0)
}
rows = {}
for name, w in MIXES.items():
    rows[name] = (ret[list(w)] * pd.Series(w)).sum(axis=1)
mix = pd.DataFrame(rows)

def stats(series):
    g = (1 + series).cumprod()
    years = len(series)
    full = series.loc[:2025]
    cagr = (1 + full).prod() ** (1 / len(full)) - 1
    return {"growth_2015_2026ytd": round(float(g.iloc[-1]), 3),
            "cagr_2015_2025": round(float(cagr) * 100, 2),
            "worst_year": int(series.idxmin()), "worst_year_ret": round(float(series.min()) * 100, 1)}

out = {
    "method": "세전·USD·수정종가(배당 재투자)·연 1회 1월 리밸런싱·연말 종가 기준 연수익. 2026은 연초~마지막 공통 거래일. BTC-USD는 현물 가격, 수수료·세금·환율·국내 매수 경로 제외. D안의 10%는 이자 0 현금.",
    "data_last_date": str(last.date()),
    "source": "Yahoo Finance via yfinance " + yf.__version__,
    "prices_sha256": hashlib.sha256((ROOT / "data" / "prices.csv").read_bytes()).hexdigest(),
    "asset_year_returns_pct": {str(y): {k: round(float(v) * 100, 1) for k, v in ret.loc[y].items()} for y in ret.index},
    "mix_year_returns_pct": {str(y): {k: round(float(v) * 100, 1) for k, v in mix.loc[y].items()} for y in mix.index},
    "mix_stats": {k: stats(mix[k]) for k in mix},
    "btc_contribution_2022_pctp": round(float(ret.loc[2022, "BTC-USD"]) * 10, 1),
    "btc_total_loss_cap_pctp": -10.0,
}
(ROOT / "data" / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: out[k] for k in ["data_last_date", "mix_stats", "btc_contribution_2022_pctp"]}, ensure_ascii=False, indent=1))
print(pd.DataFrame(out["mix_year_returns_pct"]).T.join(pd.DataFrame(out["asset_year_returns_pct"]).T).to_string())

# --- 시작 시점별 연복리 (고점 매수 착시 점검) & 일별 경로 최대 낙폭(연 1회 1월 리밸런싱) ---
px = raw[["SCHD", "QLD"]].dropna().join(raw["BTC-USD"], how="left").ffill()
px = px.loc["2015-01-01":]

def daily_path(w):
    vals, cur, hold = [], 1.0, None
    prev_year = None
    for d, row in px.iterrows():
        if prev_year != d.year:
            hold = {k: cur * w[k] / row[k] for k in w if w[k] > 0}
            cash = cur * (1 - sum(w.values()))
            prev_year = d.year
        cur = sum(hold[k] * row[k] for k in hold) + cash
        vals.append(cur)
    return pd.Series(vals, index=px.index)

paths = {}
for name, w in MIXES.items():
    p = daily_path(w)
    if name == "D_dopamine_zero":
        pass
    paths[name] = p
paths = pd.DataFrame(paths)
mdd = {k: round(float((paths[k] / paths[k].cummax() - 1).min()) * 100, 1) for k in paths}
mdd_date = {k: str((paths[k] / paths[k].cummax() - 1).idxmin().date()) for k in paths}

def cagr_from(y0):
    sub = mix.loc[y0:2025]
    return {k: round(float(((1 + sub[k]).prod()) ** (1 / len(sub)) - 1) * 100, 1) for k in mix}

out["daily_mdd_pct"] = mdd
out["daily_mdd_trough"] = mdd_date
out["cagr_by_start_to_2025"] = {str(y): cagr_from(y) for y in [2015, 2018, 2022]}
(ROOT / "data" / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("MDD", mdd, mdd_date)
print("CAGR by start", out["cagr_by_start_to_2025"])
